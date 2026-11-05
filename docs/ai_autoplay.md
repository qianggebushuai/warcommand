# AI 自动游玩系统（ai_autoplay）技术文档

> 目标：让多模态模型"看"游戏画面 → 生成 JSON 操作指令 → 游戏内执行器把指令
> 转换成真实鼠标/键盘操作，实现玩家可开关的自动游玩。游戏内按 **F10** 开关。

---

## 一、整体架构

```
┌─────────────── 游戏进程（每帧）────────────────┐
│ world_mixin.update → autoplay.update()         │
│   ① InputExecutor.step()  逐帧回放指令队列      │
│   ② 每 scan_interval 秒截图（vision）           │
│      ├ record_dataset=true: 截图+自动标注落盘    │
│      └ 后台线程 → VLM API → JSON 指令           │
│ ③ render_mixin.draw → autoplay.draw_hud()      │
└────────────────────────────────────────────────┘
策略上下文 = ai_autoplay/strategy/*.md（单位逻辑+打法）
           + protocol.py 生成规则 + UI 地标先验
```

| 文件 | 职责 |
|---|---|
| [protocol.py](../ai_autoplay/protocol.py) | 指令分类、校验、生成规则 |
| [input_executor.py](../ai_autoplay/input_executor.py) | 指令 → 真实鼠标/键盘（Windows SendInput，pygame 后备） |
| [vision.py](../ai_autoplay/vision.py) | 截图、UI 地标、地面真值标注、检测器加载点 |
| [strategy.py](../ai_autoplay/strategy.py) | 策略文案库加载 + prompt 组装 |
| [agent.py](../ai_autoplay/agent.py) | 总控：开关、定时扫描、校验入队、HUD |
| [strategy/](../ai_autoplay/strategy/) | 策略文案库（可随时编辑，无需重启） |
| [config.json](../ai_autoplay/config.json) | API 端点/模型/扫描周期/数据采集开关 |
| [local_policy.py](../ai_autoplay/local_policy.py) | 本地规则策略引擎（decision:"local"，零 API） |
| [direct_executor.py](../ai_autoplay/direct_executor.py) | 高级动作 → 游戏 API 直调（建造/放置/生产/攻击/占领/支援） |
| [il_dataset.py](../ai_autoplay/il_dataset.py) | 模仿学习数据管线：态势格式化、动作 token 词表、老师数据采集 |
| [neural_policy.py](../ai_autoplay/neural_policy.py) | 学生策略（decision:"neural"）：ILNet 看图+态势 → 动作 |
| [tools/train_detector.py](../tools/train_detector.py) | YOLO 检测器训练（4060 CUDA） |
| [tools/train_il.py](../tools/train_il.py) | ILNet 模仿学习训练 |

---

## 二、JSON 指令协议

模型每轮输出一个 JSON 数组，单轮最多 24 条，坐标为截图分辨率下的屏幕像素。

| type | 字段 | 说明 |
|---|---|---|
| `mouse_move` | x,y | 光标移动到固定位置 |
| `mouse_click` | x,y,button(1/3),double | 固定位置点击（1=左键选择/建造，3=右键移动/攻击/取消） |
| `mouse_down` / `mouse_up` | x,y,button | 按下 / 抬起（自定义节奏用） |
| `mouse_drag` | from[x,y], to[x,y], button | 框选部队（自动插值 8 步） |
| `wheel` | delta(±1) | 缩放/滚动 |
| `key_down` / `key_up` | key | 键盘按下 / 抬起 |
| `key_tap` | key,count(1-3) | 敲一下键 |
| `hotkey` | keys[1..3] | 组合键，如 `{"keys":["ctrl","1"]}` |
| `wait` | ms(50-3000) | 等待动画/建造 |
| `stop` | — | 模型主动请求停止自动游玩 |

校验规则（`protocol.validate_commands`）：越界坐标/未知类型/非法键名**整条丢弃**并记录日志；数组外的杂质文字自动剥离。

---

## 三、执行器（指令 → 实际操作）

- **Windows 主后端**：`ctypes SendInput` —— 绝对坐标移动光标、真实按下鼠标/键盘。
  游戏内 `pygame.mouse.get_pos()/get_pressed()` 与事件流都是真实状态，
  因此**拖拽框选**这类依赖按键状态的路径与真人操作完全一致。
- **后备后端**（非 Windows）：`pygame.mouse.set_pos + event.post`（点击/按键可用，拖拽受限）。
- 节拍：每帧 `step()` 弹出若干原子步；click 拆 `down→12帧→up`，drag 拆
  `down→8 段插值移动→up`，`wait` 用真实毫秒闸。F10 关闭即清空队列。

---

## 四、三条识别路线（训练模型的方式）

### 路线 A：VLM 端到端（默认，零训练）
整帧截图 + 策略文案库 + 生成规则 → 模型直接输出 JSON 指令。
配置 `ai_autoplay/config.json`：
```json
{
  "api_base": "https://你的OpenAI兼容端点/v1",
  "model": "gpt-4o 或微调后的多模态模型名",
  "scan_interval": 6.0
}
```
密钥用环境变量 `AUTOPLAY_API_KEY`（优先）或配置里加 `"api_key"`。

### 路线 B：微调多模态模型（LoRA SFT）
1. **采集**：`config.json` 里 `"record_dataset": true`，开自动游玩进对局——
   每轮扫描自动把截图 + 地面真值标注（单位/建筑类名、屏幕框、阵营、血量比）
   存到 `dataset/autoplay/`（`vision.project_entities` 用游戏内部坐标投影，标注零成本）；
2. **转格式**：`python tools/export_yolo_dataset.py` → YOLO `data.yaml`；
3. **训练**：
   - 检测器（识别 UI/单位 + 求屏幕坐标）：
     `yolo detect train data=dataset/yolo/data.yaml model=yolov8n.pt epochs=100`
   - 多模态 SFT：把 `dataset/autoplay/labels.jsonl` 转成
     "图像 → JSON 指令" 的对话样本（配合回放日志），用
     LLaMA-Factory / Qwen-VL 微调管线训练；
4. **接入**：
   - 检测器：`best.onnx` 放到 `ai_autoplay/detector.onnx`，
     `vision.load_detector()` 自动加载（路线 C）；
   - 微调 VLM：`config.json` 的 `model` 换成微调模型名即可（OpenAI 兼容端点或
     vLLM/ollama 本地服务）。

### 路线 C：专用检测器 + LLM 组装
`ai_autoplay/detector.onnx` 存在时，每轮先本地检测出画面中的 UI/单位框，
检测结果以文字形式并入上下文，再由 LLM 决策——省 token、低延迟。

### 本地模型一键训练（推荐：零 API 损耗闭环）
不按次调用任何 API 的完整本地方案 = **YOLO 检测器（训练出的本地模型）**
+ **本地策略引擎**（[local_policy.py](../ai_autoplay/local_policy.py)，读取游戏状态与
侧栏条目生成指令）+ 检测器识别结果作视觉校验：

```text
① 采集数据   两种方式任选：
             a) 玩家采集：config.json "record_dataset": true → F10 开自动游玩打几局（≥300 帧最佳）
             b) 合成数据（无需游玩）：python tools/synth_dataset.py --frames 400
                —— 调用游戏真实实体类渲染随机战场，画面与对局一致，标注零成本
② 一键训练   python tools/train_detector.py            （pip install ultralytics onnx onnxruntime）
             GPU 用户先装 CUDA 版 torch：
               pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cu121
             然后加 --device 0（4060 笔记本 60 轮 640px 约数分钟）：
               python tools/train_detector.py --epochs 60 --imgsz 640 --batch 16 --device 0
             → 自动导出 YOLO 格式 → 训练 YOLOv8n → 导出 ONNX
             → 产出 ai_autoplay/detector.onnx + detector_names.json
③ 切换决策   config.json: "decision": "local"          （关键一步）
④ 游玩       F10 开启——全程本地推理，零网络调用
```

`decision` 两种取值：
| 值 | 推理方式 | 网络调用 | 适用 |
|---|---|---|---|
| `vlm`（默认） | 截图发给 OpenAI 兼容端点（远程 API 或本地 vLLM/ollama） | 有（本地端点则零费用） | 想要大模型级别的战术理解 |
| `local` | [local_policy.py](../ai_autoplay/local_policy.py) 纯本地规则策略（反击/建造/生产三阶段，策略同 `strategy/playbook.md` 精简版） | 完全无 | 零损耗、离线、低配机器 |

说明：`local` 模式当前从游戏内部状态（资金/电力/侧栏条目/实体真值投影）读取信息，
精度是"上帝视角"级的；训练出的检测器负责"图像识别"部分（结果注入执行日志并作校验）。
想让策略引擎完全靠检测器输出决策，需在训练时把类别扩展为"类名+阵营"
（如 `M1A2_red`），修改 `tools/export_yolo_dataset.py` 的类别归并逻辑即可。

---

## 四点五、模仿学习：让神经网络学会决策（decision:"neural"）

前面三条路线解决"识别"，模仿学习解决"决策"——用现有规则策略引擎（老师）
自动生成训练对，训练一个轻量决策网络（学生）直接从画面+态势输出动作。

### 数据流

```
① 采集（零人工标注）
   config.json: {"decision": "local", "direct": true, "il_collect": true}
   → F10 挂机，每个扫描周期落盘 (截图PNG, 态势文本sit, 老师动作JSON)
   → dataset/il/images/s*.png + samples.jsonl
② 训练（4060 上数小时）
   python tools/train_il.py --epochs 30 --batch 8 --device 0
   → ai_autoplay/il_model.pt
③ 部署
   config.json: {"decision": "neural"}
   → ILNet 看图+态势 → 自回归生成动作 token → 解码 JSON → direct_executor
```

### 态势文本（师生共用同一格式，保证训练/推理同分布）

```
F7000                             资金
B factory x1 power_plant x2       我方建筑（类型×数量）
U harvester x3 m1a2 x1            我方单位
N oilderrick@X31 Y23              中立可占领建筑（世界坐标 50 桶量化）
En m1a2@X36 Y39                   敌方单位
Eb bastion@X36 Y39                敌方建筑
```

### 动作词表与网络

- 动作 token：`DO_BUILD/DO_PLACE/DO_PRODUCE/DO_ATTACK/DO_SUPPORT/DO_APC`
  + `P_<payload>`（建造/生产对象）+ `X0..49/Y0..49`（坐标桶）+ `<sep>/<stop>`
- 网络 ILNet：resnet18 图像塔(256维) + 词嵌入 GRU 态势塔(256维)
  → TransformerDecoder×2 自回归生成，参数量 ~13M，推理毫秒级
- 训练：teacher forcing 交叉熵，PyTorch 2.2 + CUDA（Python 3.8 兼容）

### 与其他决策模式对比

| decision | 决策者 | 延迟 | 上限 |
|---|---|---|---|
| `local` | 规则引擎（老师） | 0 | 规则水平，行为可预测 |
| `neural` | ILNet（学生） | ~10ms | 模仿老师；数据够时可泛化出新序列 |
| `vlm` | 多模态大模型 | 秒级 | 最高，可读策略文案库 |

注意：学生数据越多越好（建议 50+ 局、10 万+ 样本）；欠拟合时会出现
重复动作（如连续 apc_transport），direct_executor 天然幂等，无副作用。

---

## 五、游戏接入点

| 位置 | 内容 |
|---|---|
| [controllers/input_mixin.py](../controllers/input_mixin.py) | `F10` 创建/开关 AutoPlayManager |
| [game/world_mixin.py](../game/world_mixin.py) `update()` | 每帧 `autoplay.update()`（异常自动熔断关闭） |
| [game/render_mixin.py](../game/render_mixin.py) `draw()` | PLAYING 时画 HUD 状态条 |

仅在 `state == "PLAYING"` 时扫描与执行；非对局状态 HUD 显示"等待对局"。

---

## 六、安全与调优

- 单轮 ≤24 条指令；执行队列 >60 步自动丢旧轮（防模型刷屏积压）；
- `wait` 上限 3 秒；坐标越界整条丢弃；
- 模型调用在后台线程，超时 45 秒，失败不影响游戏本体；
- `scan_interval` 建议先设 8–10 秒观察行为，再逐步调小；
- 策略库（`strategy/*.md`）改完即时生效（每轮扫描重新读取）。
