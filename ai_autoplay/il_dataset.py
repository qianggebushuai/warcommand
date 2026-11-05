# -*- coding: utf-8 -*-
"""模仿学习（Imitation Learning）数据管线。

老师：LocalPolicy（上帝视角规则引擎）——每轮决策动作作为标签
学生：ILNet（tools/train_il.py 训练的轻量决策网络）——看截图+态势，模仿老师的操作

数据流：
    agent(local 模式, il_collect=true)
      → 每个扫描周期落盘 (截图PNG, 态势文本sit, 动作序列acts)
      → dataset/il/images/s*.png + samples.jsonl
    tools/train_il.py --epochs 30 --device 0
      → ai_autoplay/il_model.pt
    decision:"neural"（neural_policy.py）
      → 学生网络看图+态势 → 生成动作 JSON → direct_executor 执行

态势文本（situation，师生共用同一格式，保证训练/推理同分布）：
    F7000                                资金
    B power_plant x2 mining x1 factory x1   我方建筑（类型×数量）
    U harvester x3 m1a2 x1                  我方单位
    N OilDerrick@35,15                      中立可占领建筑（50bin 坐标）
    En M1A2@60,60; M1A2@61,61               敌方单位
    Eb Bastion@65,65                        敌方建筑
坐标一律世界坐标 → 50 桶量化（WORLD_WIDTH/HEIGHT 10000 → 0..49）。
"""
import os
import json
import time
import threading

from pygame.math import Vector2 as vec

try:
    from core.settings import WORLD_WIDTH, WORLD_HEIGHT
except Exception:                                            # 独立脚本训练时兜底
    WORLD_WIDTH, WORLD_HEIGHT = 10000, 10000

N_BIN = 50
SAMPLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dataset', 'il')
SAMPLE_JSONL = os.path.join(SAMPLE_DIR, 'samples.jsonl')

# 动作词表固定部分
SPEC_TOKENS = ['<pad>', '<bos>', '<sep>', '<stop>']
ACTION_TOKENS = ['DO_BUILD', 'DO_PLACE', 'DO_PRODUCE',
                 'DO_ATTACK', 'DO_SUPPORT', 'DO_APC',
                 'DO_DEFEND', 'DO_AIRRAID', 'DO_MOVE', 'DO_TAB', 'DO_CAMERA']
COORD_TOKENS = ['X%d' % i for i in range(N_BIN)] + ['Y%d' % i for i in range(N_BIN)]
# 态势文本的固定词（此前 sit 词不在词表里 → 全变 <unk>，模型等于看不见态势，
# 只有 Y 坐标命中。补齐后资金分桶/段前缀/计数/类名才能真正进入 GRU）
SIT_SIDE_TOKENS = ['B', 'U', 'N', 'En', 'Eb', 'R', 'W', 'Mb', 'More']
SIT_COUNT_TOKENS = ['x%d' % i for i in range(1, 31)]
SIT_MONEY_TOKENS = ['F%d' % i for i in range(41)]        # 资金 500 金一桶，0~2万+
SIT_CLASS_TOKENS = [
    # 我方/敌方建筑
    'base', 'power_plant', 'mining', 'factory', 'airfield', 'barracks',
    'radar', 'research', 'laser_turret', 'aa_turret', 'bunker',
    'missile_def', 'tech_center', 'shipyard', 'bastion', 'oilderrick',
    'prototype_gen', 'turret',
    # 单位（含中立列车/敌人）
    'rifleman', 'rocket', 'combat_engineer', 'shotgunner', 'sniper',
    'mech', 'waver', 'm1a2', 't14', 'type99', 'apc', 'armored',
    'fighterjet', 'attackplane', 'helicopter', 'wz10', 'kirov',
    'harvester', 'traincarriage', 'armoredtrain', 'engineer', 'drone',
]
MONEY_BIN = 500              # 资金分桶粒度（金）
MAX_ACT_TOKENS = 24          # 单轮最多生成的动作 token 数


def _bin(v, total):
    """世界坐标 → 0..N_BIN-1 桶。"""
    return max(0, min(N_BIN - 1, int(v * N_BIN / max(1, total))))


def fmt_pos(x, y):
    return 'X%d Y%d' % (_bin(x, WORLD_WIDTH), _bin(y, WORLD_HEIGHT))


def format_situation(game, dets=None):
    """把游戏状态格式化为态势文本（训练=内部真值，推理=可换成检测器输出）。"""
    try:
        money = int(game.team_resources.get(game.my_team, 0))
    except Exception:
        money = 0
    my = game.my_team
    b_count, u_count = {}, {}
    neutral, e_units, e_blds = [], [], []
    for b in getattr(game, 'all_buildings', []):
        if not getattr(b, 'alive', True):
            continue
        bt = getattr(b, 'b_type', '') or b.__class__.__name__.lower()
        if b.team == my:
            b_count[bt] = b_count.get(bt, 0) + 1
        elif b.team == 'neutral':
            if hasattr(b, 'capture_progress'):               # 可占领的战略建筑
                neutral.append('%s@%s' % (b.__class__.__name__.lower(),
                                          fmt_pos(b.pos.x, b.pos.y)))
        else:
            e_blds.append('%s@%s' % (bt, fmt_pos(b.pos.x, b.pos.y)))
    for u in getattr(game, 'all_units', []):
        if not getattr(u, 'alive', True):
            continue
        cls = u.__class__.__name__.lower()
        if u.team == my:
            u_count[cls] = u_count.get(cls, 0) + 1
        else:
            e_units.append('%s@%s' % (cls, fmt_pos(u.pos.x, u.pos.y)))
    parts = ['F%d' % min(40, money // MONEY_BIN)]   # 资金分桶：F0~F40（原 raw 值会词表爆炸）
    # R/W/Mb 必须排在实体列表前面：sit 截断 48 词，中立/敌实体多时
    # 排在最后的段落会被挤掉（R/W 曾被 16 个中立油井挤丢 → 放置时机又不可见）
    try:
        items = getattr(getattr(game, 'sidebar', None), 'all_items', None) or {}
        ready, busy = [], []
        for it in items.get('BUILD', []):
            if getattr(it, 'is_ready', False):
                ready.append(it.payload)
            elif getattr(it, 'is_building', False):
                busy.append(it.payload)
        for it in items.get('UNIT', []):
            if getattr(it, 'is_building', False):
                busy.append(it.payload)
        if ready:
            parts.append('R ' + ' '.join(sorted(ready)))
        if busy:
            parts.append('W ' + ' '.join(sorted(busy)))
    except Exception:
        pass
    # 己方基地坐标（此前只有计数：B base x1——学生学 build/place
    # 落点时连"基地在哪"都不知道）
    for b in getattr(game, 'all_buildings', []):
        if getattr(b, 'alive', True) and b.team == my and \
                'base' in ((getattr(b, 'b_type', '') or
                           b.__class__.__name__.lower())):
            parts.append('Mb ' + 'base@' + fmt_pos(b.pos.x, b.pos.y))
            break
    if b_count:
        parts.append('B ' + ' '.join('%s x%d' % (k, v) for k, v in sorted(b_count.items())))
    if u_count:
        parts.append('U ' + ' '.join('%s x%d' % (k, v) for k, v in sorted(u_count.items())))
    for n in neutral[:8]:                            # 中立也限量，防挤占窗口
        parts.append('N ' + n)
    for e in e_units[:8]:
        parts.append('En ' + e)
    if len(e_units) > 8:                             # 截断提示：还有多少没列出
        parts.append('More x%d' % (len(e_units) - 8))
    for e in e_blds[:8]:
        parts.append('Eb ' + e)
    if len(e_blds) > 8:
        parts.append('More x%d' % (len(e_blds) - 8))
    return ' '.join(parts)


def encode_sit_ids(sit, vocab, limit=64):
    """sit 文本 → token id 序列（训练/推理共用，保证一致性）。
    '@' 切开：'oilderrick@X15' → 'oilderrick' + 'X15'（X 坐标命中词表，
    否则黏成一词变 <unk>，X 坐标信息全部丢失）。"""
    words = sit.replace(';', ' ').replace('@', ' ').split()
    ids = [vocab.stoi.get(w, vocab.stoi['<unk>']) for w in words][:limit]
    if not ids:
        ids = [vocab.stoi['<unk>']]
    return ids


# 动作规范化顺序：老师 append 的顺序是任意的（按策略通道），但自回归学生
# 对顺序极敏感（首个 token 权重最大）——不排序则"占领/驻防"这类常发动作
# 霸占首位，建造/放置被挤丢（表现为学生从不建工厂）。建造>生产>战斗>占领。
ACT_ORDER = {'place': 0, 'build': 1, 'produce': 2, 'support': 3,
             'air_raid': 4, 'defend_base': 5, 'attack': 6, 'move': 7,
             'tab': 8, 'camera': 8, 'apc_transport': 9}


def encode_actions(acts, vocab):
    """动作 dict 列表 → token id 序列（含 <bos>/<stop>，训练标签用）。
    编码前按 ACT_ORDER 稳定排序，消除老师动作顺序的任意性。"""
    acts = sorted(acts or [], key=lambda a: ACT_ORDER.get(a.get('do'), 7))
    toks = ['<bos>']
    for a in acts or []:
        d = a.get('do')
        dmap = {'build': 'DO_BUILD', 'place': 'DO_PLACE', 'produce': 'DO_PRODUCE',
                'attack': 'DO_ATTACK', 'support': 'DO_SUPPORT',
                'apc_transport': 'DO_APC',
                'defend_base': 'DO_DEFEND', 'air_raid': 'DO_AIRRAID',
                'move': 'DO_MOVE', 'tab': 'DO_TAB', 'camera': 'DO_CAMERA'}
        dt = dmap.get(d)
        if dt is None:
            continue
        toks.append(dt)
        if a.get('payload'):
            toks.append('P_' + str(a['payload']))
        # 带坐标的动作编码 X桶/Y桶（place 带坐标即人工示范的精确落点）
        if d in ('attack', 'support', 'air_raid', 'move', 'place',
                 'camera') and a.get('world'):
            wx, wy = a['world'][:2]
            toks.extend(fmt_pos(wx, wy).split())
        toks.append('<sep>')
    toks.append('<stop>')
    return [vocab.stoi.get(t, 0) for t in toks]


def decode_tokens(ids, itos):
    """token id 序列 → 动作 dict 列表（学生网络推理输出）。
    DO_* 开新动作；P_ 填 payload；X/Y 填坐标；<sep> 结束当前动作；<stop> 停止。"""
    acts, cur = [], None
    do_map = {'DO_BUILD': 'build', 'DO_PLACE': 'place',
              'DO_PRODUCE': 'produce', 'DO_ATTACK': 'attack',
              'DO_SUPPORT': 'support', 'DO_APC': 'apc_transport',
              'DO_DEFEND': 'defend_base', 'DO_AIRRAID': 'air_raid',
              'DO_MOVE': 'move', 'DO_TAB': 'tab', 'DO_CAMERA': 'camera'}
    for i in ids:
        t = itos.get(int(i), '')
        if t == '<stop>':
            break
        if t in ('<sep>', '<bos>', '<pad>'):
            if cur is not None and _valid(cur):
                acts.append(cur)
            cur = None
            continue
        if t.startswith('DO_'):
            if cur is not None and _valid(cur):
                acts.append(cur)
            cur = {'do': do_map[t]} if t in do_map else None
            continue
        if cur is None:
            continue
        if t.startswith('P_'):
            cur['payload'] = t[2:]
        elif t.startswith('X'):
            try:
                cur['_x'] = int(t[1:])
            except ValueError:
                pass
        elif t.startswith('Y'):
            try:
                cur['_y'] = int(t[1:])
            except ValueError:
                pass
    if cur is not None and _valid(cur):
        acts.append(cur)
    return acts


def _valid(a):
    """动作完整性检查：需要坐标的补齐后确认。
    build/produce 必须有 payload；place 的 payload 可省
    （学生只说"该放了"→ 执行端放置全部就绪建筑，解决低频建筑
    （机场/雷达/兵营）payload 学不出来的问题）。"""
    d = a.get('do')
    if d in ('build', 'produce') and not a.get('payload'):
        return False
    if d in ('attack', 'support', 'air_raid', 'move'):
        if '_x' in a and '_y' in a:
            x, y = a.pop('_x'), a.pop('_y')
            a['world'] = [x * WORLD_WIDTH // N_BIN, y * WORLD_HEIGHT // N_BIN]
        if 'world' not in a:
            return False
    elif d in ('place', 'camera'):
        # 有人类示范的精确落点则还原；无坐标也合法（执行器自行搜索）
        if '_x' in a and '_y' in a:
            x, y = a.pop('_x'), a.pop('_y')
            a['world'] = [x * WORLD_WIDTH // N_BIN, y * WORLD_HEIGHT // N_BIN]
    a.pop('_x', None)
    a.pop('_y', None)
    return True


class ILVocab:
    """动作 token 词表：固定部分 + 从数据收集的 P_ payload。"""

    def __init__(self, payloads=None):
        self.tokens = (list(SPEC_TOKENS) + list(ACTION_TOKENS) + list(COORD_TOKENS)
                       + SIT_SIDE_TOKENS + SIT_COUNT_TOKENS + SIT_MONEY_TOKENS
                       + SIT_CLASS_TOKENS)
        for p in payloads or []:
            t = 'P_' + p
            if t not in self.tokens:
                self.tokens.append(t)
        if '<unk>' not in self.tokens:
            self.tokens.append('<unk>')
        self.stoi = {t: i for i, t in enumerate(self.tokens)}
        self.itos = {i: t for t, i in self.stoi.items()}

    @classmethod
    def from_jsonl(cls, path):
        payloads = set()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    for a in rec.get('acts', []):
                        if a.get('payload'):
                            payloads.add(str(a['payload']))
        return cls(sorted(payloads))

    def merge_jsonl(self, path):
        """从另一个数据源合并 payload token（多源混合训练时保证词表完整）。"""
        if not os.path.exists(path):
            return
        for p in type(self).from_jsonl(path).tokens:
            if p.startswith('P_') and p not in self.stoi:
                self.tokens.insert(len(self.tokens) - 1, p)   # <unk> 之前
        self.stoi = {t: i for i, t in enumerate(self.tokens)}
        self.itos = {i: t for t, i in self.stoi.items()}

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.tokens, f, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return cls(json.load(f))
        return cls()

    def __len__(self):
        return len(self.tokens)


class ILCollector:
    """老师数据采集器：线程安全追加 (image, sit, acts) 样本。"""

    def __init__(self, base_dir=None):
        self.dir = os.path.abspath(base_dir or SAMPLE_DIR)
        self.img_dir = os.path.join(self.dir, 'images')
        self.jsonl = os.path.join(self.dir, 'samples.jsonl')
        os.makedirs(self.img_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._n = self._count()
        self._last_sit = None       # 去重：挂机空转时局面不变，避免刷重复样本
        self._last_acts = None
        self._last_t = 0.0

    def _count(self):
        if not os.path.exists(self.jsonl):
            return 0
        with open(self.jsonl, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)

    def save(self, png_bytes, sit, acts, cam=None):
        if not acts:
            return False
        now = time.time()
        # 去重：20 秒内局面与动作都没变 → 跳过（挂机空闲不再灌重复样本；
        # 局面相同但动作不同（如冷却变化）仍会保留，那是关键学习信号）
        if (sit == self._last_sit and acts == self._last_acts
                and now - self._last_t < 20.0):
            return False
        with self._lock:
            name = 's%08d.png' % self._n
            with open(os.path.join(self.img_dir, name), 'wb') as f:
                f.write(png_bytes)
            rec = {'img': name, 'sit': sit, 'acts': acts, 't': time.time()}
            if cam:
                # 相机状态（offset/zoom/视口尺寸）：纯视觉模式的定位依据——
                # 模型靠它把"屏幕上的东西"换算回"世界坐标桶"。
                # 旧样本无此字段，训练端按镜头居中默认值处理。
                rec['cam'] = cam
            with open(self.jsonl, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            self._n += 1
            self._last_sit, self._last_acts, self._last_t = sit, acts, now
        return True
