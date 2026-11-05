# -*- coding: utf-8 -*-
"""i18n 中英双语 UI 文本框架。

用法：
    from core.i18n import tr, tr_name, tr_desc, set_language, get_language
    tr("menu.title")                -> 按当前语言返回
    tr("go.wins", name="AI")        -> 带格式化参数
    tr_name("Factory")              -> 侧栏条目名翻译（缺失回退原文）
    tr_desc("Provides Power")       -> 侧栏条目描述翻译（缺失回退原文）

语言持久化在 config/lang.json（打包版写在 exe 旁 config/，与 save.json 同基准）。
默认语言 zh（中文）。
"""
import json
import os
import sys

# ---------------------------------------------------------------- 路径
if getattr(sys, 'frozen', False):
    # 打包版：配置写 exe 旁 config/（_MEIPASS 退出即清空，不可写档）
    _ROOT = os.path.dirname(sys.executable)
else:
    # i18n.py 位于 core/ 下，上一级即项目根
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG_PATH = os.path.join(_ROOT, 'config', 'lang.json')

# ---------------------------------------------------------------- 文本表
# 键约定：模块前缀.用途；zh/en 两份必须齐全，tr 缺键时回退键名本身（便于发现漏配）
STRINGS = {
    # --- 通用 ---
    "esc.quit":       {"zh": "按 ESC 退出", "en": "Press ESC to Quit"},
    "common.back":    {"zh": "返回", "en": "BACK"},
    "common.start":   {"zh": "开始游戏", "en": "START GAME"},
    "common.leave":   {"zh": "离开", "en": "LEAVE"},
    "common.close":   {"zh": "关闭", "en": "CLOSE"},
    "common.ready":   {"zh": "就绪", "en": "READY"},
    "common.restart": {"zh": "重新开始", "en": "RESTART"},
    "common.quit":    {"zh": "退出", "en": "QUIT"},
    "common.loading": {"zh": "加载中... {pct}%", "en": "LOADING... {pct}%"},

    # --- 主菜单 / 登录背景 ---
    "menu.subtitle_update": {"zh": "多人模式更新中！", "en": "MULTIPLAYER IS UPDATING!"},
    "menu.title":           {"zh": "单人游戏", "en": "SINGLE PLAYER"},
    "menu.arena":           {"zh": "竞技场", "en": "ARENA"},
    "menu.fog_arena":       {"zh": "迷雾竞技场", "en": "FOG ARENA"},
    "menu.pve_define":      {"zh": "自定义遭遇战", "en": "PVE - DEFINE"},
    "menu.campaign":        {"zh": "战役", "en": "CAMPAIGN"},
    "menu.bombard_on":      {"zh": "轰炸模式：开", "en": "BOMBARD: ON"},
    "menu.bombard_off":     {"zh": "轰炸模式：关", "en": "BOMBARD: OFF"},
    "menu.tutorial":        {"zh": "新手教程", "en": "TUTORIAL"},
    "menu.back_login":      {"zh": "返回登录", "en": "BACK TO LOGIN"},
    "menu.funds":           {"zh": "军费: {n}", "en": "Funds: {n}"},
    "menu.funds_tag":       {"zh": "竞技场军费", "en": "ARENA FUNDS"},
    "menu.faction":         {"zh": "阵营: {f}", "en": "FACTION: {f}"},

    # --- 教程 ---
    "tut.title": {"zh": "新手教程", "en": "TUTORIAL"},
    "tut.1": {"zh": "- WASD 移动视角，滚轮缩放。", "en": "- WASD to Move Camera, Scroll to Zoom."},
    "tut.2": {"zh": "- 左键选择单位，右键移动/攻击。", "en": "- Left Click to Select Unit, Right Click to Move/Attack."},
    "tut.3": {"zh": "- 点击基地建造建筑或招募步兵。", "en": "- Click Base to Build Structures or Recruit Infantry."},
    "tut.4": {"zh": "- 建造工厂出坦克，机场出飞机。", "en": "- Build Factory for Tanks, Airfield for Aircraft."},
    "tut.5": {"zh": "- 建造雷达解锁支援技能（AC130、导弹）。", "en": "- Build Radar for Special Support (AC130, Missile)."},
    "tut.6": {"zh": "- 占领油井和工厂获得额外资源。", "en": "- Capture Oil Derricks & Factories for extra resources."},
    "tut.7": {"zh": "- 研究中心解锁防御与升级。", "en": "- Research Center unlocks defenses & upgrades."},
    "tut.8": {"zh": "- 生存下来并摧毁敌方基地！", "en": "- Survive and Destroy Enemy Base!"},

    # --- 结算 ---
    "go.defeat":   {"zh": "战败", "en": "DEFEAT"},
    "go.victory":  {"zh": "胜利！", "en": "VICTORY!"},
    "go.draw":     {"zh": "平局！", "en": "DRAW!"},
    "go.wins":     {"zh": "{name} 获胜！", "en": "{name} WINS!"},
    "go.rematch":  {"zh": "申请重赛", "en": "REQUEST REMATCH"},
    "go.waiting":  {"zh": "等待中...", "en": "WAITING..."},
    "go.accept":   {"zh": "接受重赛！", "en": "ACCEPT REMATCH!"},

    # --- 提示 ---
    "alert.low_power": {"zh": "电力不足！", "en": "LOW POWER!"},
    "alert.queue_full": {"zh": "队列已满", "en": "QUEUE FULL"},

    # --- 设置 ---
    "set.title":        {"zh": "设置", "en": "SETTINGS"},
    "set.volume":       {"zh": "音量：", "en": "Volume:"},
    "set.fullscreen":   {"zh": "全屏：", "en": "Fullscreen:"},
    "set.window_size":  {"zh": "窗口尺寸：", "en": "Window Size:"},
    "set.cur_full":     {"zh": "当前：全屏 {w}x{h}", "en": "Current: FULLSCREEN {w}x{h}"},
    "set.cur_window":   {"zh": "当前：窗口 {w}x{h}", "en": "Current: WINDOW {w}x{h}"},
    "set.language":     {"zh": "语言：", "en": "Language:"},

    # --- 登录界面 ---
    "login.id_title":    {"zh": "登录", "en": "IDENTIFICATION"},
    "login.reg_title":   {"zh": "注册", "en": "ENLISTMENT"},
    "login.server":      {"zh": "服务器地址 (IP:端口)", "en": "SERVER ADDRESS (IP:PORT)"},
    "login.username":    {"zh": "用户名", "en": "USERNAME"},
    "login.password":    {"zh": "密码", "en": "PASSWORD"},
    "login.btn_login":   {"zh": "登录", "en": "LOGIN"},
    "login.btn_reg":     {"zh": "注册", "en": "REGISTER"},
    "login.create_acc":  {"zh": "注册账号", "en": "Create Account"},
    "login.back":        {"zh": "返回登录", "en": "Back to Login"},
    "login.guest":       {"zh": "游客登录", "en": "GUEST LOGIN"},
    "login.st_empty":    {"zh": "字段不能为空", "en": "Fields cannot be empty"},
    "login.st_connect":  {"zh": "连接中...", "en": "Connecting..."},
    "login.st_fail":     {"zh": "登录失败（检查服务器/用户名/密码）", "en": "Login Failed (Check Server/User/Pass)"},
    "login.st_reg_ok":   {"zh": "注册成功！请登录。", "en": "Registration Successful! Please Login."},
    "login.st_error":    {"zh": "错误：{e}", "en": "Error: {e}"},

    # --- 多人大厅 ---
    "lobby.title":       {"zh": "多人大厅", "en": "MULTIPLAYER LOBBY"},
    "lobby.host":        {"zh": "[主机] {name}", "en": "[HOST] {name}"},
    "lobby.max_players": {"zh": "人数上限：{n}", "en": "Max Players: {n}"},
    "lobby.mode":        {"zh": "模式：{m}", "en": "Mode: {m}"},
    "lobby.start_money": {"zh": "初始资金：", "en": "Start Money:"},
    "lobby.income_rate": {"zh": "收入速率：", "en": "Income Rate:"},
    "lobby.ready":       {"zh": "已准备！", "en": "READY!"},
    "lobby.not_ready":   {"zh": "未准备", "en": "NOT READY"},

    # --- 自定义遭遇战 ---
    "skirmish.title":      {"zh": "自定义遭遇战", "en": "CUSTOM SKIRMISH"},
    "skirmish.load_error": {"zh": "加载失败", "en": "Load Error"},
    "skirmish.my_faction": {"zh": "我的阵营：", "en": "My Faction:"},
    "skirmish.ai_count":   {"zh": "AI 数量：", "en": "AI Count:"},
    "skirmish.game_modes": {"zh": "游戏模式：", "en": "Game Modes:"},

    # --- 世界内文本（render_mixin） ---
    "w.ac130_target":  {"zh": "AC-130 目标", "en": "AC-130 Target"},
    "w.missile_target": {"zh": "导弹目标", "en": "Missile Target"},
    "w.paused":        {"zh": "游戏暂停", "en": "GAME PAUSED"},
    "w.launch_hint":   {"zh": "左键点击发射", "en": "LEFT CLICK TO LAUNCH"},
    "w.iron_ready":    {"zh": "铁幕就绪", "en": "IRON CURTAIN READY"},
    "w.airdrop_zone":  {"zh": "空投区", "en": "Airdrop Zone"},
    "w.waiting":       {"zh": "等待玩家中...", "en": "WAITING FOR PLAYERS..."},
    "w.spectating":    {"zh": "观战中", "en": "SPECTATING"},
    "w.constructed":   {"zh": "建造完成", "en": "CONSTRUCTED"},
    "w.upgraded":      {"zh": "{t} 升级完成！", "en": "{t} UPGRADED!"},
    "w.base_rebuilt":  {"zh": "基地重建！", "en": "BASE REBUILT!"},
    "w.enemy_tag":     {"zh": "[敌方]", "en": "[ENEMY]"},
    "w.eliminated":    {"zh": "你已被淘汰！", "en": "YOU HAVE BEEN ELIMINATED!"},

    # --- 竞技场 ---
    "ar.alert_deploy":  {"zh": "军费不足，无法部署！", "en": "Not enough funds to deploy!"},
    "ar.alert_intel":   {"zh": "军费不足，买不起情报！", "en": "Not enough funds for intel!"},
    "ar.alert_bet":     {"zh": "军费不足，无法押注！", "en": "Not enough funds to bet!"},
    "ar.alert_relief":  {"zh": "军费不足，指挥部发放救济金至 100", "en": "Funds below 100, HQ issued relief to 100"},
    "ar.alert_deploy1": {"zh": "请先部署至少一个单位！", "en": "Deploy at least one unit first!"},
    "ar.funds":         {"zh": "军费: {n}", "en": "Funds: {n}"},
    "ar.streak":        {"zh": "连胜 {n}", "en": "Win Streak {n}"},
    "ar.bet_hint":      {"zh": "选择你认为获胜的一方（点击面板押注）", "en": "Pick the winner (click a panel to bet)"},
    "ar.bet_invest":    {"zh": "本次将投入: {n} 军费", "en": "This bet: {n} funds"},
    "ar.intel":         {"zh": "敌军情报", "en": "ENEMY INTEL"},
    "ar.unknown":       {"zh": "？？？", "en": "???"},
    "ar.intel_hint":    {"zh": "购买情报可查看敌军编成", "en": "Buy intel to view enemy lineup"},
    "ar.vs":            {"zh": "红方 {l}  vs  {r} 蓝方", "en": "Red {l}  vs  {r} Blue"},
    "ar.cur_funds":     {"zh": "当前军费: {n}", "en": "Current Funds: {n}"},
    "ar.relief_tip":    {"zh": "军费不足 100，下一轮将发放救济金至 100", "en": "Funds below 100; relief to 100 next round"},
    "ar.total_cost":    {"zh": "总造价: {n}", "en": "Total Cost: {n}"},
    "ar.bet_here":      {"zh": "点击押注此方", "en": "Click to bet on this side"},
    "ar.team_red":      {"zh": "红方军团", "en": "RED LEGION"},
    "ar.team_blue":     {"zh": "蓝方军团", "en": "BLUE LEGION"},
    "ar.none":          {"zh": "无人", "en": "Nobody"},
    "ar.fight_hint":    {"zh": "战斗中… {s} 秒后毒圈开始收缩  |  滚轮缩放 / WASD 或左键拖拽平移",
                         "en": "Fighting... zone shrinks in {s}s  |  Scroll to zoom / WASD or drag to pan"},
    "ar.zone_shrink":   {"zh": "毒圈收缩中 {p}%——离开毒雾！", "en": "Zone shrinking {p}% — get out of the fog!"},
    "ar.advantage":     {"zh": "兵力占优", "en": "Superior Force"},
    "ar.disadvantage":  {"zh": "兵力劣势", "en": "Inferior Force"},
    "ar.even":          {"zh": "势均力敌", "en": "Evenly Matched"},
    "ar.units_est":     {"zh": "单位数量: {n}    预估: {t}", "en": "Units: {n}    Outlook: {t}"},
    "ar.next_round":    {"zh": "下一轮（继续押注）", "en": "Next Round (Keep Betting)"},
    "ar.exit_keep":     {"zh": "退出（保留军费）", "en": "Exit (Keep Funds)"},
    "ar.sep":           {"zh": "，", "en": ", "},
    "ar.watch_bonus":   {"zh": "，观战奖励 +50", "en": ", spectate bonus +50"},
    "ar.result_draw":   {"zh": "平 局", "en": "DRAW"},
    "ar.result_draw_d": {"zh": "双方同归于尽，押注退还", "en": "Mutual destruction, bet refunded"},
    "ar.result_win":    {"zh": "押注正确！军费翻倍", "en": "Bet Correct! Funds Doubled"},
    "ar.result_win_d":  {"zh": "{name} 获胜，返还 {n} 军费", "en": "{name} wins, {n} funds returned"},
    "ar.result_lose":   {"zh": "押注失败", "en": "Bet Failed"},
    "ar.result_lose_d": {"zh": "{name} 获胜，{n} 军费充公", "en": "{name} wins, {n} funds confiscated"},
    "ar.result_nobet":  {"zh": "本轮未押注", "en": "No Bet This Round"},
    "ar.result_nobet_d": {"zh": "{name} 获胜", "en": "{name} wins"},
    "ar.fog_kills":     {"zh": "击杀 {n} 个敌军单位 +{r} 军费", "en": "Killed {n} enemy units +{r} funds"},
    "ar.fog_hold":      {"zh": "防 线 守 住 ！", "en": "LINE HELD!"},
    "ar.fog_lost":      {"zh": "防 线 失 守", "en": "LINE LOST"},
    "ar.fog_win":       {"zh": "胜利奖励 +{n}", "en": "Victory bonus +{n}"},
    "ar.fog_lose":      {"zh": "失败罚金 -{n}", "en": "Defeat penalty -{n}"},
    "ar.fog_spent":     {"zh": "（本轮布防花费 {n} 军费不退还）", "en": "(Deployment cost {n} not refunded)"},
    "ar.title_standard": {"zh": "铁血竞技场", "en": "IRON ARENA"},
    "ar.bet_on":        {"zh": "押注 {name} {n} 军费", "en": "Bet {n} on {name}"},
    "ar.exit_save":     {"zh": "退出竞技场（保存军费）", "en": "Exit Arena (Save Funds)"},
    "ar.exit_save2":    {"zh": "退出（保存军费）", "en": "Exit (Save Funds)"},
    "ar.empty":         {"zh": "（空）", "en": "(empty)"},
    "ar.buy_intel":     {"zh": "购买情报（{n} 军费）", "en": "Buy Intel ({n} funds)"},
    "ar.round":         {"zh": "第 {n} 轮", "en": "Round {n}"},
    "ar.skip_bet":      {"zh": "不押注直接开战", "en": "Start Without Betting"},
    "ar.intel_bought":  {"zh": "情报已购", "en": "Intel Owned"},
    "ar.fight_btn":     {"zh": "开 战 ！", "en": "FIGHT!"},
    "ar.fog_deploy_tip": {"zh": "右侧侧栏点选兵种 → 点击左侧己方半区落位（右键/再点一次取消）",
                          "en": "Pick units in right sidebar → click your half to deploy (right-click to cancel)"},
    "ar.fog_stat":      {"zh": "选中: {s}({p})    已部署 {d} / 已花费 {n}",
                         "en": "Selected: {s}({p})    Deployed {d} / Spent {n}"},
    "ar.none2":         {"zh": "无", "en": "None"},

    # --- 战役 / 更新日志 ---
    "ws.select":     {"zh": "选择任务开始战役", "en": "Select a mission to start the campaign"},
    "ws.back":       {"zh": "← 返回主菜单", "en": "← Back to Menu"},
    "ws.objectives": {"zh": "任务目标", "en": "Mission Objectives"},
    "ul.title":      {"zh": "更新日志", "en": "UPDATE LOG"},
}

# ---------------------------------------------------------------- 侧栏覆盖表
# 侧栏条目按英文原名查表：zh 提供中文，en 直接回退原文（表里无需重复英文）
ITEM_NAMES = {
    "Power": "电站", "Factory": "工厂", "Airfield": "机场", "Radar": "雷达",
    "Shipyard": "船坞", "Tech Lab": "科技实验室", "Mining": "矿场",
    "AA Gun": "防空炮", "Laser": "激光塔", "Missile Def": "导弹防御",
    "Bunker": "地堡", "Barracks": "兵营", "Fortress": "堡垒",
    "BlackShroud": "黑幕发生器", "Prototype": "原型工厂",
    "Iron Curtain": "铁幕装置", "Nuke Silo": "核弹发射井", "CIWS": "近防系统",
    "Tech Center": "科技中心", "REBUILD BASE": "重建基地",
    "Rifleman": "步兵", "Rocket": "火箭兵", "Engineer": "工程师",
    "Shotgunner": "霰弹兵", "APC": "装甲运兵车", "Armored": "装甲车",
    "Sniper": "狙击手", "Mech": "机甲", "ShockwaveVehicle": "冲击波战车",
    "Heli": "直升机", "Attacking Heli": "武装直升机", "FighterJet": "战斗机",
    "AttackPlane": "攻击机", "HeavyTransport": "重型运输机", "Airship": "基洛夫飞艇",
    "MissileBoat": "导弹艇", "AAFrigate": "防空护卫舰",
    "LaserDestroyer": "激光驱逐舰", "MissileCruiser": "导弹巡洋舰",
    "Type 99": "99式坦克", "DroneCarrier": "无人机航母", "TankCarrier": "坦克运载车",
    "HIMARS": "海马斯火箭炮", "StealthHeli": "隐形直升机", "Hind": "雌鹿",
    "TerminatorIFV": "终结者步战车", "AC-130": "AC-130 炮艇机",
    "Missile": "导弹", "Airdrop": "空投", "Battleship": "战列舰",
}
ITEM_DESCS = {
    "Provides Power": "提供电力", "Produces Vehicles": "生产载具",
    "Produces Aircraft": "生产飞机", "Unlocks Support & Minimap": "解锁支援与雷达图",
    "Produces Naval Units": "生产海军单位", "Unlocks Advanced Tech": "解锁高级科技",
    "Generates Income": "产出资金", "Anti-Air Defense": "防空防御",
    "Anti-Ground Laser": "对地激光", "Intercepts Missiles": "拦截导弹",
    "commom defense": "基础防御", "2nd Infantry Line": "第二步兵生产线",
    "Heavy quad-turret defense": "四炮塔重型防御", "create a disturbing area": "制造干扰区域",
    "Base for Superweapons": "超级武器基座", "Invulnerability Shield": "无敌护盾",
    "Devastating Rocket": "毁灭性火箭", "short defense": "近程防御",
    "Unlocks Advanced Units": "解锁高级单位", "Construct a new MCV/Base": "重建新的基地/MCV",
    "Basic Infantry": "基础步兵", "Anti-Vehicle/Air Infantry": "反载具/防空步兵",
    "Repair & Capture Buildings": "修理与占领建筑", "Close Range AOE": "近程范围伤害",
    "Transport Infantry": "运载步兵", "Light Vehicle": "轻型载具",
    "Main Battle Tank": "主战坦克", "Long Range Anti-Infantry": "远程反步兵",
    "Heavy Walker": "重型步行机", "blow enemy away": "击退敌人",
    "Attack Helicopter": "攻击直升机", "Heavy heli": "重型直升机",
    "jet used for template but heavy strike": "重型打击喷气机",
    "jet used for strike vichile": "对地打击喷气机",
    "carry mechs and drop them": "运载机甲并空投", "Heavy Bomber Airship": "重型轰炸飞艇",
    "Naval Missile Platform": "海军导弹平台", "laser damage get higher by time": "激光伤害随时间提升",
    "Heavy Tank": "重型坦克", "spawner": "无人机母舰", "carry tank": "搭载坦克",
    "Rocket Arty": "火箭炮", "hightech heli": "高科技直升机", "Gunship": "武装炮艇",
    "The descendnet of doom": "毁灭使者", "Aerial Gunship Support": "空中炮艇支援",
    "Long Range Cruise Missile": "远程巡航导弹", "Paratrooper Reinforcements": "伞兵增援",
    "Control the Battleship": "控制战列舰",
}
# 侧栏标签页 tooltip（键=标签名）
TAB_INFO = {
    "BUILD": {"zh": ("建造", "建造建筑"), "en": ("BUILD", "Construct Buildings")},
    "UNIT":  {"zh": ("单位", "训练单位"), "en": ("UNIT", "Train Units")},
    "SUPP":  {"zh": ("支援", "支援技能"), "en": ("SUPP", "Support Powers")},
    "ETC":   {"zh": ("其他", "特殊选项"), "en": ("ETC", "Special Options")},
}
# 自定义遭遇战的游戏模式勾选项（键=模式名，en 显示大写原文）
MODE_NAMES = {
    "normal": "标准", "cards": "卡牌", "economy": "经济", "bombard": "轰炸",
}

# ---------------------------------------------------------------- 语言状态
current_language = "zh"
_LANG_DISPLAY = {"zh": "中文", "en": "English"}


def _load_lang():
    """启动时从 config/lang.json 读语言，缺文件/坏文件用默认 zh。"""
    global current_language
    try:
        with open(LANG_PATH, 'r', encoding='utf-8') as f:
            lang = json.load(f).get("language")
        if lang in ("zh", "en"):
            current_language = lang
    except Exception:
        pass


_load_lang()


def get_language():
    return current_language


def get_language_display():
    """语言按钮上显示的名字（始终以该语言自身文字显示）。"""
    return _LANG_DISPLAY.get(current_language, current_language)


def set_language(lang, save=True):
    """切换语言并即时持久化；lang 取值 zh / en。"""
    global current_language
    if lang not in ("zh", "en"):
        return
    current_language = lang
    if save:
        try:
            os.makedirs(os.path.dirname(LANG_PATH), exist_ok=True)
            with open(LANG_PATH, 'w', encoding='utf-8') as f:
                json.dump({"language": lang}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def toggle_language():
    """中文/英文来回切，返回切换后的语言。"""
    set_language("en" if current_language == "zh" else "zh")
    return current_language


def tr(key, **kw):
    """取当前语言文本；缺失回退键名本身，格式化失败回退原文。"""
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(current_language) or entry.get("zh") or key
    if kw:
        try:
            text = text.format(**kw)
        except Exception:
            pass
    return text


def tr_name(name):
    """侧栏条目名：中文模式查覆盖表，英文模式回退原文。"""
    if current_language == "zh":
        return ITEM_NAMES.get(name, name)
    return name


def tr_desc(desc):
    """侧栏条目描述：中文模式查覆盖表，英文模式回退原文。"""
    if current_language == "zh":
        return ITEM_DESCS.get(desc, desc)
    return desc


def tr_tab(name):
    """侧栏标签页 tooltip：返回 (显示名, 描述)。"""
    info = TAB_INFO.get(name)
    if info:
        pair = info.get(current_language) or info["en"]
        return pair
    return name, ""


def tr_mode(name):
    """自定义遭遇战模式名：中文模式查表，英文模式大写原文。"""
    if current_language == "zh":
        return MODE_NAMES.get(name, name)
    return name.upper()
