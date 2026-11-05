# -*- coding: utf-8 -*-
"""模仿学习训练脚本：ILNet（截图+态势 → 动作 token 序列）。

用法：
    python tools/train_il.py --epochs 30 --batch 8 --device 0
    # 数据不足时提示先采集：config.json 设 "il_collect": true，F10 挂机

架构（Python 3.8 / torch 2.2 兼容，4060 数小时可训）：
    图像塔  resnet18(pretrained)      → 256 维画面特征
    态势塔  词 embedding + GRU        → 256 维态势特征
    融合    [img;sit] 作为 memory
    解码器  TransformerDecoder x2     → 自回归生成动作 token
    输出    动作词表（DO_*/P_*/X*/Y*）→ 解码回 JSON 动作
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image

from ai_autoplay.il_dataset import (SAMPLE_JSONL, SAMPLE_DIR, ILVocab,
                                    encode_actions, MAX_ACT_TOKENS)

IL_MODEL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'ai_autoplay', 'il_model.pt')
IMG_SIZE = 224
D_MODEL = 256


class ILSamples(Dataset):
    def __init__(self, jsonls, vocab):
        self.vocab = vocab
        self.tf = transforms.Compose([
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        self.recs = []
        for jsonl in (jsonls if isinstance(jsonls, list) else [jsonls]):
            img_dir = os.path.join(os.path.dirname(os.path.abspath(jsonl)),
                                   'images')
            with open(jsonl, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    img = os.path.join(img_dir, rec.get('img', ''))
                    if not (os.path.exists(img) and rec.get('sit')
                            and rec.get('acts')):
                        continue
                    try:                  # 损坏截图（半路写盘/删除）直接剔除
                        Image.open(img).verify()
                    except Exception:
                        print('[IL] 跳过损坏截图: %s' % rec.get('img'))
                        continue
                    self.recs.append((img, rec['sit'], rec['acts']))

    def __len__(self):
        return len(self.recs)

    def __encode_sit(self, sit):
        from ai_autoplay.il_dataset import encode_sit_ids
        return torch.tensor(encode_sit_ids(sit, self.vocab), dtype=torch.long)

    def __getitem__(self, i):
        img, sit, acts = self.recs[i]
        x = self.tf(Image.open(img).convert('RGB'))
        sit_ids = self.__encode_sit(sit)
        tgt = torch.tensor(encode_actions(acts, self.vocab)[:MAX_ACT_TOKENS + 2],
                           dtype=torch.long)
        return x, sit_ids, tgt


def collate(batch):
    xs, sits, tgts = zip(*batch)
    # 目标序列右 pad，mem 无需 pad（GRU 打包取末态）
    t_len = max(len(t) for t in tgts)
    s_len = max(len(s) for s in sits)
    pad = 0
    T = torch.full((len(tgts), t_len), pad, dtype=torch.long)
    for i, t in enumerate(tgts):
        T[i, :len(t)] = t
    S = torch.full((len(sits), s_len), pad, dtype=torch.long)
    for i, s in enumerate(sits):
        S[i, :len(s)] = s
    return torch.stack(xs), S, T


class ILNet(nn.Module):
    def __init__(self, vocab_size):
        super().__init__()
        try:                                                     # 预训练权重，离线时降级
            from torchvision.models import resnet18, ResNet18_Weights
            back = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
        except Exception:
            from torchvision.models import resnet18
            back = resnet18(weights=None)
        back.fc = nn.Linear(512, D_MODEL)
        self.img = back
        self.sit_emb = nn.Embedding(vocab_size, 64)
        self.sit_rnn = nn.GRU(64, D_MODEL, batch_first=True)
        self.tok_emb = nn.Embedding(vocab_size, D_MODEL)
        self.pos = nn.Embedding(MAX_ACT_TOKENS + 2, D_MODEL)
        layer = nn.TransformerDecoderLayer(D_MODEL, 4, 512,
                                           batch_first=True, dropout=0.1)
        self.dec = nn.TransformerDecoder(layer, 2)
        self.out = nn.Linear(D_MODEL, vocab_size)

    def forward(self, x, sit_ids, tgt_in):
        img_f = self.img(x).unsqueeze(1)                         # [B,1,D]
        _, h = self.sit_rnn(self.sit_emb(sit_ids))
        sit_f = h[-1].unsqueeze(1)                               # [B,1,D]
        mem = torch.cat([img_f, sit_f], dim=1)                   # [B,2,D]
        B, L = tgt_in.shape
        pos = torch.arange(L, device=tgt_in.device).unsqueeze(0).expand(B, L)
        h = self.tok_emb(tgt_in) + self.pos(pos)
        mask = nn.Transformer.generate_square_subsequent_mask(L,
                                                              device=tgt_in.device)
        y = self.dec(h, mem, tgt_mask=mask)
        return self.out(y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=30)
    ap.add_argument('--batch', type=int, default=8)
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--device', default='0')
    # 数据源：--data 指定 jsonl（可传多个逗号分隔混合，如
    # 老师样本+人工示范：--data "dataset/il/samples.jsonl,dataset/il/human/samples.jsonl"）
    ap.add_argument('--data', default=SAMPLE_JSONL)
    ap.add_argument('--out', default=IL_MODEL)
    args = ap.parse_args()

    jsonls = [p.strip() for p in args.data.split(',') if p.strip()]
    jsonls = [p for p in jsonls if os.path.exists(p)]
    if not jsonls:
        print('[IL] 无训练数据：%s 均不存在' % args.data)
        print('[IL] 先采集：config.json 设 "il_collect": true，进对局按 F10 挂机；'
              '或 F8 人工示范（dataset/il/human/）')
        return
    recs = []
    for p in jsonls:
        n = sum(1 for _ in open(p, encoding='utf-8'))
        recs.append((p, n))
    vocab = ILVocab.from_jsonl(jsonls[0])
    for p in jsonls[1:]:                       # 合并多源词表
        vocab.merge_jsonl(p)
    ds = ILSamples(jsonls, vocab)
    if len(ds) < 50:
        print('[IL] 样本仅 %d 条（<50），建议先采集更多' % len(ds))
    print('[IL] 样本 %d 条（%s），词表 %d' %
          (len(ds), ', '.join('%s:%d' % (p.replace('dataset', '…'), n)
                              for p, n in recs), len(vocab)))

    dev = 'cuda:%s' % args.device if args.device != 'cpu' and \
        torch.cuda.is_available() else 'cpu'
    print('[IL] 设备:', dev)
    dl = DataLoader(ds, batch_size=args.batch, shuffle=True,
                    collate_fn=collate, num_workers=0)

    net = ILNet(len(vocab)).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=args.lr)
    crit = nn.CrossEntropyLoss(ignore_index=0)                   # <pad> 不计损失

    for ep in range(args.epochs):
        net.train()
        tot, n = 0.0, 0
        for x, S, T in dl:
            x, S, T = x.to(dev), S.to(dev), T.to(dev)
            tgt_in, tgt_out = T[:, :-1], T[:, 1:]
            logits = net(x, S, tgt_in)
            loss = crit(logits.reshape(-1, logits.size(-1)), tgt_out.reshape(-1))
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            tot += loss.item()
            n += 1
        print('[IL] epoch %d/%d  loss %.4f' % (ep + 1, args.epochs, tot / max(1, n)))

    torch.save({'state': net.state_dict(), 'vocab': vocab.tokens},
               args.out)
    vocab.save(args.out.replace('.pt', '_vocab.json'))
    print('[IL] 模型已保存:', args.out)
    print('[IL] 启用: config.json 设 "decision": "neural"，重启游戏 F10')


if __name__ == '__main__':
    main()
