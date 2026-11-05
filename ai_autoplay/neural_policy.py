# -*- coding: utf-8 -*-
"""学生策略：ILNet 推理（decision:"neural"）。

与 local_policy（规则老师）并列的第三种决策模式：
    截图 + 态势文本 → 学生网络自回归生成动作 token → 解码 JSON → direct_executor

态势文本与老师训练时同分布（format_situation）；检测器结果可用时
叠加 "Det" 段（视觉先验），但主态势仍用内部真值保证稳定。
"""
import os
import json

import torch
import pygame

from ai_autoplay.il_dataset import (format_situation, decode_tokens,
                                    ILVocab, MAX_ACT_TOKENS)
from ai_autoplay import vision as vision_mod

IL_MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'il_model.pt')
D_MODEL = 256


class ILNet(torch.nn.Module):
    """与 tools/train_il.py 完全一致的网络结构（推理端独立定义避免依赖 tools）。"""

    def __init__(self, vocab_size):
        super().__init__()
        try:
            from torchvision.models import resnet18, ResNet18_Weights
            back = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
        except Exception:
            from torchvision.models import resnet18
            back = resnet18(weights=None)
        back.fc = torch.nn.Linear(512, D_MODEL)
        self.img = back
        self.sit_emb = torch.nn.Embedding(vocab_size, 64)
        self.sit_rnn = torch.nn.GRU(64, D_MODEL, batch_first=True)
        self.tok_emb = torch.nn.Embedding(vocab_size, D_MODEL)
        self.pos = torch.nn.Embedding(MAX_ACT_TOKENS + 2, D_MODEL)
        layer = torch.nn.TransformerDecoderLayer(D_MODEL, 4, 512,
                                                 batch_first=True, dropout=0.0)
        self.dec = torch.nn.TransformerDecoder(layer, 2)
        self.out = torch.nn.Linear(D_MODEL, vocab_size)


class NeuralPolicy:
    """加载 il_model.pt，greedy 解码动作。推理失败自动返回空动作并上报状态。"""

    def __init__(self, model_path=None, device='cuda'):
        path = model_path or IL_MODEL
        ckpt = torch.load(path, map_location='cpu')
        self.vocab = ILVocab()
        self.vocab.tokens = ckpt.get('vocab') or self.vocab.tokens
        self.vocab.stoi = {t: i for i, t in enumerate(self.vocab.tokens)}
        self.vocab.itos = {i: t for t, i in self.vocab.stoi.items()}
        self.net = ILNet(len(self.vocab.tokens))
        self.net.load_state_dict(ckpt['state'])
        self.dev = device if (device != 'cpu' and torch.cuda.is_available()) else 'cpu'
        self.net.to(self.dev).eval()
        self.tf = None                                              # 惰性建
        self.last_reason = 'ILNet 已加载'

    def _prep(self, png_bytes, sit):
        from torchvision import transforms
        from PIL import Image
        import io
        if self.tf is None:
            self.tf = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406],
                                     [0.229, 0.224, 0.225])])
        img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
        x = self.tf(img).unsqueeze(0).to(self.dev)
        from .il_dataset import encode_sit_ids
        sit_ids = torch.tensor([encode_sit_ids(sit, self.vocab)],
                               dtype=torch.long, device=self.dev)
        return x, sit_ids

    def decide(self, game, png_bytes, dets=None):
        sit = format_situation(game, dets)
        x, sit_ids = self._prep(png_bytes, sit)
        B = 1
        ys = torch.full((B, 1), self.vocab.stoi['<bos>'],
                        dtype=torch.long, device=self.dev)
        with torch.no_grad():
            img_f = self.net.img(x).unsqueeze(1)
            _, h = self.net.sit_rnn(self.net.sit_emb(sit_ids))
            mem = torch.cat([img_f, h[-1].unsqueeze(1)], dim=1)
            for _ in range(MAX_ACT_TOKENS):
                L = ys.size(1)
                pos = torch.arange(L, device=self.dev).unsqueeze(0).expand(B, L)
                h = self.net.tok_emb(ys) + self.net.pos(pos)
                mask = torch.nn.Transformer.generate_square_subsequent_mask(
                    L, device=self.dev)
                logits = self.net.out(self.net.dec(h, mem, tgt_mask=mask))
                nxt = logits[:, -1].argmax(-1, keepdim=True)
                ys = torch.cat([ys, nxt], dim=1)
                if nxt.item() == self.vocab.stoi['<stop>']:
                    break
        acts = decode_tokens(ys[0].tolist(), self.vocab.itos)
        self.last_reason = 'ILNet:%d动作' % len(acts)
        return acts
