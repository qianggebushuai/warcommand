import pygame
from core.settings import *
from core.utils import resource_path, get_font
import os
import sys

# --- 1. 图鉴数据（单位 + 建筑，图片放 picture/ 或写 sprites/ 相对路径） ---
def _s(stats, atk=0, rng=None):
    """统一数值串：stats=[hp, speed, range]（settings 注入的位置列表）"""
    hp, spd, r = stats[2], stats[1], stats[0]
    return f"HP: {hp} | ATK: {atk} | RNG: {rng if rng is not None else r} | SPD: {spd}"

DIC_DATA = [
    # ================= 步兵 =================
    {
        "id": "rifleman", "name": "步枪兵", "type": "地面步兵",
        "stats": _s(RIFLEMAN_STATS, DMG_RIFLE),
        "desc": "步枪兵是一种廉价但实用的单位,成群的单位对于地面目标可造成毁灭性打击",
        "history": "",
        "img": "icon_rifleman.png", "faction": "ALL",
    },
    {
        "id": "rocket", "name": "反坦克兵", "type": "地面步兵",
        "stats": _s(ROCKET_STATS, 100),
        "desc": "反坦克火箭筒对付坦克和步兵都是较为有效的方式,但要避免脆弱的火箭兵遭受来自侧方的袭击",
        "history": "",
        "img": "icon_rocket.png", "faction": "ALL",
    },
    {
        "id": "shotgun", "name": "霰弹防爆兵", "type": "地面步兵",
        "stats": _s(SHOTGUNNER_STATS, 160),
        "desc": "'假以时日,这种推进式穿甲弹药能被派上战场...'一位政治家如此说道,而在现在,这种微小但杀伤力巨大的精密弹药被装进了霰弹枪,用于毁灭近距离的一切单位",
        "history": "",
        "img": "icon_shotgunner.png", "faction": "ALL",
    },
    {
        "id": "sniper", "name": "狙击手", "type": "地面步兵",
        "stats": _s(SNIPER_STATS, 90),
        "desc": "狙击手可以对步兵单位实现有效远程打击,但是无法对装甲单位造成有效伤害",
        "history": "",
        "img": "icon_sniper.png", "faction": "ALL",
    },
    {
        "id": "engineer", "name": "战斗工程师", "type": "地面步兵",
        "stats": _s(COMBAT_EN, 0),
        "desc": "工程师可以修复己方建筑,或是占领中立或敌方建筑,但是并没有实际攻击性",
        "history": "",
        "img": "icon_combat_engineer.png", "faction": "ALL",
    },
    # ================= 地面载具 =================
    {
        "id": "m1a2", "name": "M1A2", "type": "地面载具",
        "stats": _s(M1A2_STATS, DMG_M1A2),
        "desc": "这款服役以四十多年的坦克在正面进攻和破障方面依然发挥着重要作用",
        "history": "......",
        "img": "icon_m1a2.png", "faction": "USA",
    },
    {
        "id": "m1a2", "name": "TYPE99L", "type": "地面载具",
        "stats": f"HP: {int(M1A2_STATS[2]*0.9)} | ATK: {DMG_M1A2} | RNG: {M1A2_STATS[0]} | SPD: {M1A2_STATS[1]*1.2}",
        "desc": "中国希望新型载具能符合高机动,支援能力强的特点,而TYPE99L正是以这种理念被开发的",
        "history": "......",
        "img": "icon_type99L.png", "faction": "CHINA",
    },
    {
        "id": "m1a2", "name": "T28", "type": "地面载具",
        "stats": f"HP: {int(M1A2_STATS[2]*1.2)} | ATK: {DMG_M1A2} | RNG: {int(M1A2_STATS[0]*1.3)} | SPD: {M1A2_STATS[1]*0.9}",
        "desc": "新联邦在国力衰微落后对这款老式的坦克进行了现代化改进,较远的攻击范围和高伤害使其的破坏能力及其突出",
        "history": "......",
        "img": "icon_t28.png", "faction": "RUSSIA",
    },
    {
        "id": "type99", "name": "Type 99A", "type": "地面载具",
        "stats": _s(TYPE99_STATS, 180),
        "desc": "10年前被应用于中国重型坦克的核动力保证了这辆陆地巨兽依旧能保持着较高速度清除一切路上的障碍",
        "history": "......",
        "img": "icon_type99.png", "faction": "CHINA",
    },
    {
        "id": "mech", "name": "多用途机甲", "type": "地面载具",
        "stats": _s(MECH_STATS, 60),
        "desc": "在复杂的作战地形中,机甲依旧可以保持其行动力和火力支援",
        "history": "",
        "img": "sprites/units/HeavyMech/base/original_image.png", "faction": "ALL",
    },
    {
        "id": "bmpt", "name": "终结者型步战车", "type": "地面载具",
        "stats": _s(TERMINATOR_STATS, 40),
        "desc": "大多数武器的生产都是为了赢得战争,而终结者的开发则是为了终结战争",
        "history": "",
        "img": "icon_bmpt.png", "faction": "RUSSIA",
    },
    {
        "id": "himars", "name": "海马斯火箭炮", "type": "地面载具",
        "stats": _s(HIMARS_STATS, 120),
        "desc": "远程火箭炮系统能够在战线后方对敌方纵深目标实施饱和打击,发射完毕后应立即转移阵地",
        "history": "",
        "img": "icon_himars.png", "faction": "USA",
    },
    {
        "id": "tankcarrier", "name": "坦克运输车", "type": "地面载具",
        "stats": _s(TANKCARRIER_STATS, 0),
        "desc": "重型平板运输车可以将受损的坦克快速拖离前线,抢修比重建便宜得多",
        "history": "",
        "img": "sprites/units/TankCarrier/base/body_image.png", "faction": "ALL",
    },
    {
        "id": "armoredcar", "name": "轻型装甲车", "type": "地面载具",
        "stats": _s(ARMORED_STATS, 3),
        "desc": "轻型装甲车的护甲不能保护其从密集火力下生还,但其依然是较优秀的侦查单位",
        "history": "",
        "img": "icon_armored.png", "faction": "ALL",
    },
    {
        "id": "apc", "name": "多功能运输车", "type": "地面载具",
        "stats": _s(APC_STATS, 15),
        "desc": "以安全快速的方式运输大量士兵,进而实现多方面的战略部署",
        "history": "",
        "img": "icon_apc.png", "faction": "ALL",
    },
    {
        "id": "mcv", "name": "机动基地车", "type": "地面载具",
        "stats": "HP: 5000 | ATK: 0 | RNG: 0 | SPD: 1.5",
        "desc": "基地被摧毁后的最后底牌:展开即可重建指挥基地,请务必让它活着离开战区",
        "history": "",
        "img": "sprites/units/BaseBuilding/base/image.png", "faction": "ALL",
    },
    {
        "id": "harvester", "name": "W-7多功能采矿车", "type": "地面载具",
        "stats": _s(HARVESTER_STATS, 0),
        "desc": "这种矿车是为了应对火星的复杂的矿石区地形而设计的,而其在传统采矿工作的执行中也毫不逊色",
        "history": "",
        "img": "icon_harvester.png", "faction": "ALL",
    },
    # ================= 空中载具 =================
    {
        "id": "heli", "name": "轻型直升机", "type": "空中载具",
        "stats": _s(HELICOPTER_STATS, 12),
        "desc": "这种无人轻型侦查直升机旨在探测并进攻地面单位,取得空中优势",
        "history": "",
        "img": "icon_helicopter.png", "faction": "ALL",
    },
    {
        "id": "wz-10", "name": "WZ-20攻击直升机", "type": "空中载具",
        "stats": _s(WZ10_STATS, 40),
        "desc": "wz系列攻击直升机因其出色的低空飞行能力和较高的机动性在20年前开始被越来越多的国家采用,直至今天",
        "history": "",
        "img": "icon_wz10.png", "faction": "CHINA",
    },
    {
        "id": "hind", "name": "mi-24超级雌鹿", "type": "空中载具",
        "stats": _s(HIND_STATS, 55),
        "desc": "拥有坚硬的护甲和密集的火力,升级多次的mi24已经是名副其实的空中堡垒",
        "history": "",
        "img": "icon_mi24.png", "faction": "RUSSIA",
    },
    {
        "id": "stealthheli", "name": "隐形武装直升机", "type": "空中载具",
        "stats": _s(STEALHELI_STATS, 70),
        "desc": "隐身外形与消音旋翼让它能在雷达屏幕下悄然接近目标,一击脱离",
        "history": "",
        "img": "icon_stealheli.png", "faction": "USA",
    },
    {
        "id": "kirov", "name": "太空支援飞艇", "type": "空中载具",
        "stats": _s(KIROV_STATS, DMG_KIROV_BOMB),
        "desc": "太空支援飞船的主要作用是在太空环境下运载物资,但紧急时刻,它也可以用作攻城武器,投下巨大的炸弹,毁灭一切",
        "history": "",
        "img": "icon_kirov.png", "faction": "ALL",
    },
    {
        "id": "ac130", "name": "AC-130空中炮艇", "type": "空中载具",
        "stats": _s(AC130_STATS, 90),
        "desc": "侧舷阵列的重型火炮让它在盘旋中化作一座飞行堡垒,持续支援地面部队",
        "history": "",
        "img": "icon_ac130.png", "faction": "USA",
    },
    {
        "id": "paratrooper", "name": "空投运输机", "type": "空中载具",
        "stats": "HP: 400 | ATK: 0 | RNG: 0 | SPD: 4.0",
        "desc": "越过防线,将成建制的伞兵直接投放到敌军的后方关键位置",
        "history": "",
        "img": "icon_airdrop.png", "faction": "ALL",
    },
    # ================= 固定翼 =================
    {
        "id": "F35E", "name": "F35E闪电II式战斗机", "type": "固定翼",
        "stats": _s(FIGHTER_STATS, 60),
        "desc": "作为新时代的作战单位,战斗机的重要性极大的体现在取得空中优势中",
        "history": "",
        "img": "F35.png", "faction": "USA",
    },
    {
        "id": "J35A", "name": "歼35A式战斗机", "type": "固定翼",
        "stats": _s(FIGHTER_STATS, 60),
        "desc": "作为新时代的作战单位,战斗机的重要性极大的体现在取得空中优势中",
        "history": "",
        "img": "J35.png", "faction": "CHINA",
    },
    {
        "id": "SU59", "name": "SU59式战斗机", "type": "固定翼",
        "stats": _s(FIGHTER_STATS, 60),
        "desc": "作为新时代的作战单位,战斗机的重要性极大的体现在取得空中优势中",
        "history": "",
        "img": "SU57.png", "faction": "RUSSIA",
    },
    {
        "id": "FA18E", "name": "FA18E超级大黄蜂式战斗轰炸机", "type": "固定翼",
        "stats": _s(ATTACKER_STATS, 800, AA_TURRET_STATS[0]),
        "desc": "攻击机在二战后极速发展,用于对空中力量薄弱的区域进行致命打击",
        "history": "",
        "img": "FA18E.png", "faction": "USA",
    },
    {
        "id": "JH7", "name": "JH7-B飞豹式攻击机", "type": "固定翼",
        "stats": _s(ATTACKER_STATS, 800, AA_TURRET_STATS[0]),
        "desc": "攻击机在二战后极速发展,用于对空中力量薄弱的区域进行致命打击",
        "history": "歼轰7飞豹战斗轰炸机，为我国海空联合研制生产的一型战斗轰炸机，空军在后续的研发中选择了退出，恰逢特殊情况飞豹项目先后经过多次下马危机，最后好歹成功试飞量产，2000年开始服役，主要执行巡逻和打击任务,在2030年进行了推进力改进后,JH7B仍然作为最先进的超音速攻击机之一活跃在战场上",
        "img": "sprites/units/AttackPlane/base/image.png", "faction": "CHINA",
    },
    {
        "id": "SU25M", "name": "SU25-M蛙足式攻击机", "type": "固定翼",
        "stats": _s(ATTACKER_STATS, 800, AA_TURRET_STATS[0]),
        "desc": "攻击机在二战后极速发展,用于对空中力量薄弱的区域进行致命打击",
        "history": "",
        "img": "SU25M.png", "faction": "RUSSIA",
    },
    # ================= 海上载具 =================
    {
        "id": "missileboat", "name": "护卫舰", "type": "海上载具",
        "stats": "HP: 600 | ATK: 45 | RNG: 500 | SPD: 3.0",
        "desc": "护卫舰灵活,轻快,可以对短射程的单位进行有效打击",
        "history": "",
        "img": "icon_missile_boat.png", "faction": "ALL",
    },
    {
        "id": "aaboat", "name": "神盾驱逐舰", "type": "海上载具",
        "stats": _s(AABOAT_STATS, 60),
        "desc": "为了应对空中力量的指数级进化,美国将智能近防系统移植到了驱逐舰上,这个空载毁灭者就此诞生",
        "history": "",
        "img": "icon_antiairfrigate.png", "faction": "USA",
    },
    {
        "id": "missilecruiser", "name": "导弹巡洋舰", "type": "海上载具",
        "stats": _s(MissileCruiser_STATS, 90),
        "desc": "优势火力学说在海军中依然适用:一艘巡洋舰能发射的导弹自然是越大越好,越多越好",
        "history": "",
        "img": "icon_missilecruiser.png", "faction": "USA,CHINA",
    },
    {
        "id": "laserdestroyer", "name": "聚能潜艇", "type": "海上载具",
        "stats": _s(LASER_SHIP_STATS, 150),
        "desc": "激光技术一直凭借其在医学上的成就而受到称赞,直到新联邦将钴能源在激发出激光,并将这台毁灭性武器安装在了潜艇上",
        "history": "",
        "img": "icon_laserdestroyer.png", "faction": "RUSSIA",
    },
    {
        "id": "heavytransport", "name": "饕餮号运输船", "type": "海上载具",
        "stats": _s(HEAVYTRANSPORT_STATS, 0),
        "desc": "这个空中运载者不具备什么攻击性,但它可以运载数千吨的物品在航道上实现运输,或者携带大量重武器发动奇袭",
        "history": "",
        "img": "icon_heavytransport.png", "faction": "ALL",
    },
    {
        "id": "battleship", "name": "战列舰", "type": "海上载具",
        "stats": "HP: 4000 | ATK: 220 | RNG: 1400 | SPD: 0.8",
        "desc": "大舰巨炮的荣光在轨道支援时代依旧没有被遗忘,它 主炮的一次齐射足以抹平一片海岸防线",
        "history": "",
        "img": "icon_battleship_call.png", "faction": "ALL",
    },
    # ================= 生产建筑 =================
    {
        "id": "base", "name": "指挥基地", "type": "生产建筑",
        "stats": "HP: 6000 | 电力: -10",
        "desc": "整个指挥体系的核心,生产各类建筑与单位。基地被摧毁后,机动基地车可以将其重建",
        "history": "",
        "img": "sprites/units/BaseBuilding/base/image.png", "faction": "ALL",
    },
    {
        "id": "power_plant", "name": "发电厂", "type": "生产建筑",
        "stats": "HP: 900 | 造价: 300",
        "desc": "为基地提供电力,电力不足时全部生产设施将减速运转",
        "history": "",
        "img": "icon_power_plant.png", "faction": "ALL",
    },
    {
        "id": "refinery", "name": "采矿场", "type": "生产建筑",
        "stats": "HP: 1200 | 造价: 500",
        "desc": "矿石经济的起点:矿车在此卸货变现,矿场还会自动补充采矿车",
        "history": "",
        "img": "icon_mining.png", "faction": "ALL",
    },
    {
        "id": "barracks", "name": "兵营", "type": "生产建筑",
        "stats": "HP: 800 | 造价: 800",
        "desc": "训练各类步兵单位,是任何一支部队的根基",
        "history": "",
        "img": "icon_barracks.png", "faction": "ALL",
    },
    {
        "id": "warfactory", "name": "战车工厂", "type": "生产建筑",
        "stats": "HP: 1500 | 造价: 750",
        "desc": "生产坦克,机甲等地面载具,多座工厂可以并行增产",
        "history": "",
        "img": "icon_factory.png", "faction": "ALL",
    },
    {
        "id": "airfield", "name": "机场", "type": "生产建筑",
        "stats": "HP: 1000 | 造价: 1500",
        "desc": "起降固定翼战机,夺取制空权的第一步",
        "history": "",
        "img": "icon_airfield.png", "faction": "ALL",
    },
    {
        "id": "shipyard", "name": "船坞", "type": "生产建筑",
        "stats": "HP: 1200 | 造价: 1500",
        "desc": "建造与维修各类舰艇,控制水域的关键设施",
        "history": "",
        "img": "icon_shipyard.png", "faction": "ALL",
    },
    {
        "id": "research", "name": "科技中心", "type": "生产建筑",
        "stats": "HP: 1000 | 造价: 1000",
        "desc": "解锁高级兵种与更深的科技树,高科技部队的门槛",
        "history": "",
        "img": "icon_research.png", "faction": "ALL",
    },
    # ================= 防御建筑 =================
    {
        "id": "aa_turret", "name": "防空炮塔", "type": "防御建筑",
        "stats": _s(AA_TURRET_STATS, 70),
        "desc": "自动对空防御火力,专门撕碎胆敢闯入领空的飞行器",
        "history": "",
        "img": "icon_aa_turret.png", "faction": "ALL",
    },
    {
        "id": "bunker", "name": "碉堡", "type": "防御建筑",
        "stats": _s(BUNKER_STATS, 0),
        "desc": "可驻守步兵的坚固工事,为脆弱的步枪兵提供可靠掩护",
        "history": "",
        "img": "icon_bunker.png", "faction": "ALL",
    },
    {
        "id": "nuke_silo", "name": "核弹发射井", "type": "防御建筑",
        "stats": "HP: 2000 | 造价: 5000",
        "desc": "战略威慑的终极形态:装载完毕后可对任意坐标实施核打击",
        "history": "",
        "img": "icon_nuke_silo.png", "faction": "ALL",
    },
    {
        "id": "iron_curtain", "name": "铁幕装置", "type": "防御建筑",
        "stats": "HP: 1500 | 造价: 8000",
        "desc": "在短时间内让一辆单位进入无敌状态,冲阵拔点的不二之选",
        "history": "",
        "img": "icon_iron_curtain.png", "faction": "ALL",
    },
    {
        "id": "prototype_gen", "name": "原型机工厂", "type": "防御建筑",
        "stats": "HP: 1500 | 造价: 2000",
        "desc": "试制型装备的生产设施,只有最尖端的项目才会在这里组装",
        "history": "",
        "img": "icon_prototype_gen.png", "faction": "ALL",
    },
    {
        "id": "shroud_gen", "name": "迷雾发生器", "type": "防御建筑",
        "stats": "HP: 900 | 造价: 1000",
        "desc": "在周边区域散布干扰云团,让敌方的侦察手段全部失灵",
        "history": "",
        "img": "icon_shroud_gen.png", "faction": "ALL",
    },
]

# --- 1.5 背景档案（history 按 name 填充；条目里已有正文的保留，如 JH7） ---
HISTORY = {
    "步枪兵": "第三次世界大战爆发后各国兵源吃紧，标准化训练体系让新兵三周即可成建制投入战场——数量，重新成为了质量的一部分。",
    "反坦克兵": "前身是上个时代的反装甲小组，破甲弹头历经五代改进。至今它仍是坦克驾驶员的梦魇——尤其是当它出现在侧翼的时候。",
    "霰弹防爆兵": "最初为镇压矿区暴动而列装，其推进式穿甲弹头在巷战中的表现，让军方重新审视了'近距离交火'这个词的定义。",
    "狙击手": "狙击学校届届流传同一句话：一枪，一个。他们大部分时间都在潜伏，而战场上的传说往往只需要一次扣动扳机。",
    "战斗工程师": "不起眼的后勤中坚。从修复被炸塌的指挥所到策反敌方前哨，战地手册第一条写着：善待你的工程师。",
    "M1A2": "从上一场大规模战争一路走来的常青树。历经数次数字化升级，这头老兵油箱里的柴油烧了四十年，依然烧得最旺。",
    "TYPE99L": "99A 的轻量化兄弟，拆掉部分复合装甲换来机动性。军方的定位很简单：跑得快，打得准，够用。",
    "T28": "新联邦接手的老古董。国力衰微买不起新坦克，工程师们给它换了新火控和加长身管——老树发新芽，一炮一个准。",
    "Type 99A": "核动力装甲平台的成功之作。反应堆小型化让它甩掉了油料补给队，成为装甲集群里永远冲在第一个的那一个。",
    "多用途机甲": "双足行走系统的立项曾被国会称为军费黑洞，直到它第一次背着全套装备翻过了坦克无法通行的山地。",
    "终结者型步战车": "名字来源于一部老电影。设计哲学极简而暴力：用压倒性的火力密度，让'掩护步兵'这个概念本身变得多余。",
    "海马斯火箭炮": "'打了就跑'的艺术大师。从收到坐标到发射完毕再消失在公路尽头，整个过程比敌方雷达刷新一次的时间还短。",
    "坦克运输车": "没有人在意它，直到前线的坦克趴了窝。抢修营的老兵说：一辆平板拖车的价值，等于半条坦克生产线。",
    "轻型装甲车": "侦察营的老伙计。装甲薄得像纸，但速度就是它最好的装甲——等敌人看清它时，往往已经来不及开火了。",
    "多功能运输车": "把一个班的士兵完整送到目的地，听起来不算丰功伟绩——直到你在没有它的战场上数了数幸存者。",
    "机动基地车": "战争史上最昂贵的'车辆'。当基地化为焦土，它是整支军队最后的火种。保护它，如同保护你的旗帜。",
    "W-7多功能采矿车": "为火星殖民地的复杂矿脉地形而设计，调回地球战场后意外地如鱼得水——毕竟挖矿和打仗，都需要一个够硬的前铲。",
    "轻型直升机": "无人驾驶的侦察小蜜蜂。造价低到指挥官舍得成群撒出去，而敌人往往在击落第三架之后才意识到它们在做什么。",
    "WZ-20攻击直升机": "武直家族的中坚。贴着树梢的飞行方式让地面防空机枪形同虚设，二十年的持续改进让它历久弥新。",
    "mi-24超级雌鹿": "从上个世纪的山地飞到第三次世界大战的平原。能载八名士兵还硬抗火箭弹的'飞行步战车'，是俄系暴力美学的极致。",
    "隐形武装直升机": "档案级别：绝密。官方从未承认它的存在——直到某次夜袭之后，幸存的哨兵坚称自己'什么都没看见'。",
    "太空支援飞艇": "本该航行在火星航道上的货运巨兽，被战时动员令召回大气层。当它投下货舱里的'货物'，没有人笑得出来。",
    "AC-130空中炮艇": "侧舷一排火炮，绕着目标画圈就是一座不会疲倦的火力堡垒。地面部队最爱喊的空中支援，没有之一。",
    "空投运输机": "防线上最坚固的一点，往往从头顶被攻破。它把整整一个连队，送到了敌人自认为'绝对安全'的后方。",
    "F35E闪电II式战斗机": "闪电II 的深度改进型。换装自适应循环发动机与新一代传感器，依然是那个'先看到你，先打你'的规则改变者。",
    "歼35A式战斗机": "歼击机家族的新锐。隐身修形配合翼下重载挂点，制空与反舰一肩挑——太平洋上空的新守门人。",
    "SU59式战斗机": "SU-57 的深度魔改型。新联邦把最后的预算全塞进了机炮与机动性——近距缠斗，它没有对手。",
    "FA18E超级大黄蜂式战斗轰炸机": "航母甲板上的多面手。从舰队防空到浅纵深遮断，四十年的服役史证明'多用途'从来不是妥协。",
    "JH7-B飞豹式攻击机": "歼轰7飞豹战斗轰炸机，为我国海空联合研制生产的一型战斗轰炸机，空军在后续的研发中选择了退出，恰逢特殊情况飞豹项目先后经过多次下马危机，最后好歹成功试飞量产，2000年开始服役，主要执行巡逻和打击任务,在2030年进行了推进力改进后,JH7B仍然作为最先进的超音速攻击机之一活跃在战场上",
    "SU25-M蛙足式攻击机": "地面部队的老朋友。皮实、迟钝、抗揍——它不追求优雅，它追求的是每次都能带着弹孔返航。",
    "护卫舰": "近海冲突的万金油。船小好调头，导弹管够——大国海军看不上它，小国海军离不开它。",
    "神盾驱逐舰": "当空中威胁的进化速度超过火炮的反应极限，答案是把整个防空指挥所搬上驱逐舰——四面阵一开，苍蝇也飞不进来。",
    "导弹巡洋舰": "优势火力学说的忠实信徒。垂直发射井里的每一枚导弹都在重复同一个真理：齐射，即正义。",
    "聚能潜艇": "钴能源激发的高能激光连海水都拦不住——它上浮的那三秒，就是敌方舰队余生的最后三秒。",
    "饕餮号运输船": "地效飞行原理的巨型货船，战时被征用为重装备快速投送平台——一张嘴，吞下一个装甲营。",
    "战列舰": "导弹时代曾被判死刑，轨道支援时代又活了过来。九门主炮齐射时，整条海岸线都会想起什么叫大舰巨炮。",
    "指挥基地": "一切从这里开始：发电机的嗡鸣、生产线的轰响、出兵门的开合。指挥官的字典里，它是必须活到最后的单位。",
    "发电厂": "整个基地的心脏。它安静地燃烧，直到某天被炸停——然后所有人都会想起'电力配给'这四个字的意思。",
    "采矿场": "矿石经济的第一环。矿车进进出出的轰鸣就是基地的心跳——老兵们管它叫'会下金蛋的鹅'。",
    "兵营": "新兵进入战场的第一站。教官的吼声、起床号、永远差一双的作训靴——所有精锐都从这里起步。",
    "战车工厂": "生产线昼夜不停，履带的轰鸣从装配台一路传到前线——多一座工厂，就多一路钢铁洪流。",
    "机场": "跑道尽头的塔台决定着制空权的归属。地勤最骄傲的一句话：我们的战机，从来不会在跑道上等敌人。",
    "船坞": "龙门吊下的钢铁巨兽逐艘下水。控制了水域就控制了战场的腰线，而船坞就是这条腰线的支点。",
    "科技中心": "穿着白大褂的'战斗人员'。他们不开枪，但他们解锁的每一项技术，都会让敌人的下一个战术过时。",
    "防空炮塔": "自动装填，全天候待命。飞行员之间流传着一句忠告：低空进入它的射界，和在赌桌上 all-in 没有区别。",
    "碉堡": "混凝土的诚实哲学：不挪窝，不投降。驻进步兵之后它就不再是个土堆，而是防线上啃不动的那颗牙。",
    "核弹发射井": "威慑的具象化。它存在的意义最好是永远待命——可一旦发射盖开启，谈判桌上的规则将被彻底重写。",
    "铁幕装置": "试验型力场发生器。短短几秒的无敌，足够一辆坦克穿过整条交叉火力带——前提是，你算准了时间。",
    "原型机工厂": "保密级别最高的厂区。从这里驶出的每一台装备，十年后都会成为对手情报部门的主要研究课题。",
    "迷雾发生器": "让敌人的雷达屏幕飘满雪花。侦察机拍到的永远是同一片'普通的空地'——直到装甲集群从那里涌出。",
}
for _d in DIC_DATA:
    _h = _d.get("history", "")
    if not _h or _h == "......":
        _d["history"] = HISTORY.get(_d["name"], "档案缺失。")


class DictionaryUI:
    def __init__(self, game):
        self.game = game
        self.active = False

        # 布局配置
        self.margin = 50
        self.list_w = 300
        self.detail_x = self.margin + self.list_w + 20
        self.detail_w = SCREEN_WIDTH - self.detail_x - self.margin

        # 列表区域
        self.list_rect = pygame.Rect(self.margin, 100, self.list_w, SCREEN_HEIGHT - 150)
        self.item_height = 50

        # 滚动相关
        self.scroll_y = 0
        self.max_scroll = max(0, len(DIC_DATA) * self.item_height - self.list_rect.height)

        # 当前选中
        self.selected_idx = 0

        # 中文字体统一走 get_font（simhei，含中文字形；部分机器 SysFont 枚举注册表会崩、
        # Font(None) 无中文字形——中文一律走 get_font）
        self.font_title = get_font(40)
        self.font_title.set_bold(True)
        self.font_item = get_font(18)
        self.font_detail_h = get_font(32)
        self.font_detail_h.set_bold(True)
        self.font_detail_body = get_font(20)

        # 筛选状态
        self.filter_faction = "ALL"
        self.filter_type = "ALL"

        # 缓存筛选结果 (初始化为全部)
        self.visible_data = DIC_DATA
        self.btn_back = pygame.Rect(self.margin, SCREEN_HEIGHT - 45, 100, 30)

        # 主界面入口按钮（右上角，与设置齿轮并排；menu/login 通用）
        self.btn_open = pygame.Rect(SCREEN_WIDTH - 110, 20, 40, 40)
        self.img_cache = {}  # 图片缓存
        self.list_rect = pygame.Rect(self.margin, 150, self.list_w, SCREEN_HEIGHT - 200)

        # 筛选按钮（横幅下方，横幅只占右侧详情区不会遮挡）
        self.btn_faction = pygame.Rect(self.margin, 112, 140, 30)
        self.btn_type = pygame.Rect(self.margin + 150, 112, 140, 30)

        # 顶部横幅（图鉴数据库 HUD 风，程序化生成于 picture/；只铺右侧详情区）
        self.banner = None
        try:
            b = pygame.image.load(resource_path("picture/banner_database.png")).convert_alpha()
            self.banner = pygame.transform.smoothscale(b, (self.detail_w, 88))
        except Exception:
            self.banner = None

    def apply_filter(self):
        self.visible_data = []
        for item in DIC_DATA:
            # 1. 阵营筛选
            item_fac = item.get("faction", "ALL")
            if self.filter_faction != "ALL":
                # 如果单位是通用的，或者阵营匹配，就保留
                if item_fac != "ALL" and self.filter_faction not in item_fac.split(","):
                    continue

            # 2. 类型筛选
            if self.filter_type != "ALL":
                if item.get("type", "").upper() != self.filter_type:
                    continue

            self.visible_data.append(item)

        # 重置滚动和选中
        self.scroll_y = 0
        self.selected_idx = 0
        # 更新 max_scroll
        self.max_scroll = max(0, len(self.visible_data) * self.item_height - self.list_rect.height)

    def get_image(self, img_name):
        if not img_name:
            return None
        if img_name in self.img_cache:
            return self.img_cache[img_name]

        if img_name.startswith("sprites/"):
            path = resource_path(img_name)
        else:
            path = resource_path(f"picture/{img_name}")
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                # 统一缩放到 300x200 (或者保持比例)
                img = pygame.transform.scale(img, (300, 200))
                self.img_cache[img_name] = img
                return img
            except Exception:
                pass
        return None

    def handle_input(self):
        m_pos = pygame.mouse.get_pos()
        events = pygame.event.get()
        pass

    def handle_event(self, event):
        # 1. 在主界面点击打开
        if not self.active:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.btn_open.collidepoint(event.pos):
                    self.active = True
                    self._open_origin = self.game.state  # 关闭时回到打开前界面
                    self.game.state = "DIC"  # 切换游戏状态，暂停其他逻辑
                    return True
            return False

        # 2. 图鉴界面交互
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # 左键
                if self.btn_back.collidepoint(event.pos):
                    self.close()
                    return True

                # 列表点击
                if self.list_rect.collidepoint(event.pos):
                    # 计算点击了第几项 (考虑滚动)
                    rel_y = event.pos[1] - self.list_rect.y + self.scroll_y
                    idx = int(rel_y // self.item_height)
                    if 0 <= idx < len(DIC_DATA):
                        self.selected_idx = idx
                        # (可选) 播放音效

            # 滚轮滚动
            elif event.button == 4:  # Up
                self.scroll_y = max(0, self.scroll_y - 30)
            elif event.button == 5:  # Down
                self.scroll_y = min(self.max_scroll, self.scroll_y + 30)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            m_pos = pygame.mouse.get_pos()

            # 切换阵营
            if self.btn_faction.collidepoint(m_pos):
                opts = ["ALL", "USA", "CHINA", "RUSSIA"]
                curr_idx = opts.index(self.filter_faction)
                self.filter_faction = opts[(curr_idx + 1) % len(opts)]
                self.apply_filter()
                return True

            # 切换类型
            if self.btn_type.collidepoint(m_pos):
                opts = ["ALL", "地面步兵", "地面载具", "空中载具", "固定翼", "海上载具", "生产建筑", "防御建筑", "多功能", "支援"]
                curr_idx = opts.index(self.filter_type)
                self.filter_type = opts[(curr_idx + 1) % len(opts)]
                self.apply_filter()
                return True

            # 列表点击 (注意：现在是点击 visible_data)
            if self.list_rect.collidepoint(m_pos):
                rel_y = m_pos[1] - self.list_rect.y + self.scroll_y
                idx = int(rel_y // self.item_height)
                if 0 <= idx < len(self.visible_data):
                    self.selected_idx = idx
                return True
        return True

    def close(self):
        self.active = False
        # 回到打开前的界面（主菜单/登录），默认登录页
        self.game.state = getattr(self, '_open_origin', 'LOGIN')

    def draw(self, screen):
        # 1. 绘制入口按钮 (如果未激活)
        if not self.active:
            # 只在主菜单/登录界面显示（战地风圆角按钮 + 书本图标 + hover 高亮）
            if self.game.state in ("LOGIN", "MENU"):
                hov = self.btn_open.collidepoint(pygame.mouse.get_pos())
                c = (70, 78, 90) if hov else (45, 50, 58)
                bc = (235, 235, 240) if hov else (150, 155, 165)
                pygame.draw.rect(screen, c, self.btn_open, border_radius=8)
                pygame.draw.rect(screen, bc, self.btn_open, 2, border_radius=8)
                # 书本图标：对开的两页
                cx, cy = self.btn_open.centerx, self.btn_open.centery
                pygame.draw.rect(screen, bc, (cx - 13, cy - 9, 11, 18), 1, border_radius=2)
                pygame.draw.rect(screen, bc, (cx + 2, cy - 9, 11, 18), 1, border_radius=2)
                pygame.draw.line(screen, bc, (cx, cy - 9), (cx, cy + 9), 1)
                pygame.draw.line(screen, bc, (cx - 11, cy - 4), (cx - 4, cy - 4), 1)
                pygame.draw.line(screen, bc, (cx + 4, cy - 4), (cx + 11, cy - 4), 1)
            return

        # 2. 绘制图鉴界面
        screen.fill((30, 32, 35))  # 深色背景

        # 顶部横幅（只铺右侧详情区，标题压在横幅上；左侧筛选按钮不受遮挡）
        if self.banner:
            screen.blit(self.banner, (self.detail_x, 15))
        title = self.font_title.render("UNIT DATABASE", True, YELLOW)
        screen.blit(title, (self.detail_x + 24, 24))
        pygame.draw.rect(screen, (60, 60, 70), self.btn_faction)
        pygame.draw.rect(screen, WHITE, self.btn_faction, 1)
        txt = self.font_item.render(f"{self.filter_faction}", True, WHITE)
        screen.blit(txt, (self.btn_faction.x + 5, self.btn_faction.y + 5))

        pygame.draw.rect(screen, (60, 60, 70), self.btn_type)
        pygame.draw.rect(screen, WHITE, self.btn_type, 1)
        txt = self.font_item.render(f"{self.filter_type}", True, WHITE)
        screen.blit(txt, (self.btn_type.x + 5, self.btn_type.y + 5))

        # --- 左侧列表 (使用 visible_data) ---
        list_h = len(self.visible_data) * self.item_height
        list_surf = pygame.Surface((self.list_w, max(1, list_h)))  # 防止0高度
        list_surf.fill((40, 42, 45))

        for i, item in enumerate(self.visible_data):
            rect = pygame.Rect(0, i * self.item_height, self.list_w, self.item_height)

            # 选中高亮
            color = (60, 70, 80) if i == self.selected_idx else (40, 42, 45)

            pygame.draw.rect(list_surf, color, rect)
            pygame.draw.rect(list_surf, (80, 80, 90), rect, 1)  # 分割线

            # 名字
            txt = self.font_item.render(item['name'], True, WHITE)
            list_surf.blit(txt, (10, i * self.item_height + 10))

            # 类型标签 (右对齐)
            type_txt = self.font_item.render(item['type'], True, (150, 150, 150))
            list_surf.blit(type_txt, (self.list_w - type_txt.get_width() - 10, i * self.item_height + 10))

        # 裁剪并绘制到屏幕
        sub_rect = pygame.Rect(0, self.scroll_y, self.list_w, self.list_rect.height)
        # 防止 sub_rect 超出 list_surf
        if sub_rect.bottom > list_h:
            sub_rect.height = list_h - sub_rect.top
        if sub_rect.height > 0:
            screen.blit(list_surf.subsurface(sub_rect), self.list_rect.topleft)

        # 绘制滚动条指示器
        if self.max_scroll > 0:
            sb_h = self.list_rect.height * (self.list_rect.height / list_h)
            sb_y = self.list_rect.y + (self.scroll_y / self.max_scroll) * (self.list_rect.height - sb_h)
            pygame.draw.rect(screen, (100, 100, 100), (self.list_rect.right + 5, sb_y, 5, sb_h), border_radius=2)

        # --- 右侧详情 ---
        if self.visible_data and self.selected_idx < len(self.visible_data):
            data = self.visible_data[self.selected_idx]

            # 1. 名字与类型（faction 右对齐详情区右缘，避免与名字/类型重叠）
            #    名字过长时降级到小一号字体，避免与右侧 faction 撞行
            if self.font_title.size(data['name'])[0] > self.detail_w - 10:
                name_s = self.font_detail_h.render(data['name'], True, WHITE)
            else:
                name_s = self.font_title.render(data['name'], True, WHITE)
            screen.blit(name_s, (self.detail_x, 112))
            type_s = self.font_item.render(f"Type: {data['type']}", True, CYAN)
            screen.blit(type_s, (self.detail_x, 166))
            if data.get("faction"):
                faction_s = self.font_item.render(f"Faction: {data['faction']}", True, RED)
                screen.blit(faction_s,
                            faction_s.get_rect(topright=(self.detail_x + self.detail_w, 170)))

            # 2. 数值面板
            stats_bg = pygame.Rect(self.detail_x, 200, self.detail_w, 40)
            pygame.draw.rect(screen, (50, 50, 60), stats_bg, border_radius=5)
            stat_s = self.font_item.render(data['stats'], True, YELLOW)
            screen.blit(stat_s, (self.detail_x + 10, 210))

            # 3. 图片展示
            img_rect = pygame.Rect(self.detail_x, 255, 300, 200)

            # 尝试加载图片
            img_name = data.get("img")
            img_surf = self.get_image(img_name)

            if img_surf:
                screen.blit(img_surf, img_rect)
                pygame.draw.rect(screen, WHITE, img_rect, 2)  # 边框
            else:
                # 没图片，画个黑框或者占位符
                pygame.draw.rect(screen, BLACK, img_rect)
                pygame.draw.rect(screen, WHITE, img_rect, 2)
                no_img_txt = self.font_item.render("NO IMAGE", True, GRAY)
                screen.blit(no_img_txt, no_img_txt.get_rect(center=img_rect.center))

            # 4. 描述与历史
            desc_y = 480
            # 描述
            self.draw_multiline_text(screen, "Description:", self.font_detail_h, (self.detail_x, desc_y), WHITE)
            desc_y += 40
            desc_y = self.draw_multiline_text(screen, data['desc'], self.font_detail_body, (self.detail_x, desc_y), (200, 200, 200), self.detail_w)

            desc_y += 30
            # 历史
            self.draw_multiline_text(screen, "History:", self.font_detail_h, (self.detail_x, desc_y), WHITE)
            desc_y += 40
            self.draw_multiline_text(screen, data['history'], self.font_detail_body, (self.detail_x, desc_y), (180, 180, 180), self.detail_w)

        # 返回按钮
        pygame.draw.rect(screen, (150, 50, 50), self.btn_back)
        back_s = self.font_item.render("BACK", True, WHITE)
        screen.blit(back_s, back_s.get_rect(center=self.btn_back.center))

    def draw_multiline_text(self, surface, text, font, pos, color, max_width=800):
        x, y = pos
        line_height = font.get_linesize()

        # 逐字处理
        current_line = ""
        for char in text:
            test_line = current_line + char
            # 计算宽度
            w, h = font.size(test_line)

            if x + w > pos[0] + max_width:
                # 超出宽度，绘制当前行并换行
                surf = font.render(current_line, True, color)
                surface.blit(surf, (x, y))
                y += line_height
                current_line = char  # 新行从当前字开始
            else:
                current_line = test_line

        # 绘制最后一行
        if current_line:
            surf = font.render(current_line, True, color)
            surface.blit(surf, (x, y))
            y += line_height

        return y  # 返回下一次绘制的Y坐标
