# 保存为 make_heavy_sfx.py 后执行：D:\python3.8\python.exe make_heavy_sfx.py
import wave, audioop, os

root = r"g:\网游克星\真正的网游克星\warcommand"
src = os.path.join(root, "sfx", "explosions", "explo1.wav")

with wave.open(src, "rb") as w:
    nc, sw, fr, nfr = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    data = w.readframes(nfr)
print(f"源: {nc}ch {sw*8}bit {fr}Hz {nfr/fr:.2f}s")

# 1) 深沉爆炸：降采样 44100 -> 26000Hz（音调下潜 = 厚重感）
deep, _ = audioop.ratecv(data, sw, nc, fr, 26000, None)
out1 = os.path.join(root, "sfx", "explosions", "deep_explo1.wav")
with wave.open(out1, "wb") as w:
    w.setnchannels(nc); w.setsampwidth(sw); w.setframerate(26000)
    w.writeframes(deep)
print("deep_explo1.wav 完成")

# 2) 坦克炮击低音：取开头片段 + 手动淡出（audioop 无 fade，分片乘递减系数）
for name, secs in (("deep_heavy1.wav", 0.45), ("deep_heavy2.wav", 0.62)):
    cut = deep[: int(26000 * secs) * sw * nc]
    pieces = 40
    step = max(1, len(cut) // pieces)
    chunks = []
    for i in range(0, len(cut), step):
        seg = cut[i:i + step]
        factor = max(0.0, 1.0 - i / len(cut))
        chunks.append(audioop.mul(seg, sw, factor))
    faded = b"".join(chunks)
    out = os.path.join(root, "sfx", "weapons", name)
    with wave.open(out, "wb") as w:
        w.setnchannels(nc); w.setsampwidth(sw); w.setframerate(26000)
        w.writeframes(faded)
    print(name, "完成")