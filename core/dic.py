import pygame
from core.settings import *
import os
import sys

# 辅助函数 (复用)
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'): base_path = sys._MEIPASS
    else: base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- 1. 图鉴数据 (可以在这里补充历史背景) ---
DIC_DATA = [
    {
        "id": "rifleman", "name": "步枪兵", "type": "地面步兵",
        "stats": f"HP: {RIFLEMAN_STATS[2]} | ATK: {DMG_RIFLE} | RNG: {RIFLEMAN_STATS[0]} | SPD: {RIFLEMAN_STATS[1]}",
        "desc": "步枪兵是一种廉价但实用的单位,成群的单位对于地面目标可造成毁灭性打击",
        "history": "",
        "img":"icon_rifleman.png","faction":"ALL",
    },
    {
        "id": "m1a2", "name": "M1A2", "type": "地面载具",
        "stats": f"HP: {M1A2_STATS[2]} | ATK: {DMG_M1A2} | RNG: {M1A2_STATS[0]} | SPD :{M1A2_STATS[1]}",
        "desc": "这款服役以四十多年的坦克在正面进攻和破障方面依然发挥这重要作用",
        "history": "......",
        "img":"icon_m1a2.png","faction":"USA",
    },
    {
        "id": "m1a2", "name": "TYPE99L", "type": "地面载具",
        "stats": f"HP: {M1A2_STATS[2]*0.9} | ATK: {DMG_M1A2} | RNG: {M1A2_STATS[0]} | SPD :{M1A2_STATS[1]*1.2}",
        "desc": "中国希望新型载具能符合高机动,支援能力强的特点,而TYPE99L正是以这种理念被开发的",
        "history": "......",
        "img":"icon_type99L.png","faction":"CHINA",
    },
    {
        "id": "m1a2", "name": "T28", "type": "地面载具",
        "stats": f"HP: {M1A2_STATS[2]*1.2} | ATK: {DMG_M1A2} | RNG: {M1A2_STATS[0]*1.3} | SPD :{M1A2_STATS[1]*0.9}",
        "desc": "新联邦在国力衰微落后对这款老式的坦克进行了现代化改进,较远的攻击范围和高伤害使其的破坏能力及其突出",
        "history": "......",
        "img":"icon_T28.png","faction":"RUSSIA",
    },
    {
        "id": "type99", "name": "Type 99A", "type": "地面载具",
        "stats": f"HP: {1500} | ATK: {90*2} | RNG: {M1A2_STATS[0]*1.3} | SPD :{M1A2_STATS[1]*0.9}",
        "desc": "10年前被应用于中国重型坦克的核动力保证了这辆陆地巨兽依旧能保持着较高速度清除一切路上的障碍",
        "history": "......",
        "img":"icon_type99.png","faction":"CHINA",
    },
    {
        "id": "kirov", "name": "太空支援飞艇", "type": "空中载具",
        "stats": f"HP: {KIROV_STATS[2]} | ATK: {DMG_KIROV_BOMB} | RNG: {KIROV_STATS[0]}|SPD:{KIROV_STATS[1]}",
        "desc": "太空支援飞船的主要作用是在太空环境下运载物资,但紧急时刻,它也可以用作攻城武器,投下巨大的炸弹,毁灭一切",
        "history": "",
        "img":"icon_kirov.png","faction":"ALL",
    },
    {
        "id": "apc", "name": "多功能运输车", "type": "地面载具",
        "stats": f"HP: {APC_STATS[2]} | ATK: {15} | RNG: {APC_STATS[0]} |SPD:{APC_STATS[1]} ",
        "desc": "以安全快速的方式运输大量士兵,进而实现多方面的战略部署",
        "history": "",
        "faction": "ALL",
        "img":"icon_apc_.png",
    },
    {
        "id": "armoredcar", "name": "轻型装甲车", "type": "地面载具",
        "stats": f"HP: {ARMORED_STATS[2]} | ATK: {3} | RNG: {ARMORED_STATS[0]} |SPD:{ARMORED_STATS[1]} ",
        "desc": "轻型装甲车的护甲不能保护其从密集火力下生还,但其依然是较优秀的侦查单位",
        "history": "",
        "img":"icon_armored.png","faction":"ALL",
    },

    {
        "id": "rocket", "name": "反坦克兵", "type": "地面步兵",
        "stats": f"HP: {ROCKET_STATS[2]} | ATK: {100} | RNG: {ROCKET_STATS[0]} |SPD:{ROCKET_STATS[1]} ",
        "desc": "反坦克火箭筒对付坦克和步兵都是较为有效的方式,但要避免脆弱的火箭兵遭受来自侧方的袭击",
        "history": "",
        "img":"icon_rocket.png","faction":"ALL",
    },

    {
        "id": "shotgun", "name": "霰弹防爆兵", "type": "地面步兵",
        "stats": f"HP: {SHOTGUNNER_STATS[2]} | ATK: {8*20} | RNG: {SHOTGUNNER_STATS[0]} |SPD:{SHOTGUNNER_STATS[1]} ",
        "desc": "'假以时日,这种推进式穿甲弹药能被派上战场...'一位政治家如此说道,而在现在,这种微小但杀伤力巨大的精密弹药被装进了霰弹枪,用于毁灭近距离的一切单位",
        "history": "",
        "img":"icon_SHOTGUNNER.png","faction":"ALL",
    },

    {
        "id": "sniper", "name": "狙击手", "type": "地面步兵",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "狙击手可以对步兵单位实现有效远程打击,但是无法对装甲单位造成有效伤害",
        "history": "",
        "img":"icon_sniper.png","faction":"ALL",
    },

    {
        "id": "engineer", "name": "战斗工程师", "type": "地面步兵",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "工程师可以修复己方建筑,或是占领中立或敌方建筑,但是并没有实际攻击性",
        "history": "",
        "img":"icon_engineer.png","faction":"ALL",
    },

    {
        "id": "heli", "name": "轻型直升机", "type": "空中载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "这种无人轻型侦查直升机旨在探测并进攻地面单位,取得空中优势",
        "history": "",
        "img":"icon_helicopter.png","faction":"ALL",
    },

    {
        "id": "F35E", "name": "F35E闪电II式战斗机", "type": "固定翼",
        "stats": f"HP: {FIGHTER_STATS[2]} | ATK: {60} | RNG: {FIGHTER_STATS[0]} |SPD:{FIGHTER_STATS[1]} ",
        "desc": "作为新时代的作战单位,战斗机的重要性极大的体现在取得空中优势中",
        "history": "",
        "img":"F35.png","faction":"USA",
    },

    {
        "id": "J35A", "name": "歼35A式战斗机", "type": "固定翼",
        "stats": f"HP: {FIGHTER_STATS[2]} | ATK: {60} | RNG: {FIGHTER_STATS[0]} |SPD:{FIGHTER_STATS[1]} ",
        "desc": "作为新时代的作战单位,战斗机的重要性极大的体现在取得空中优势中",
        "history": "",
        "img":"J35.png","faction":"CHINA",
    },

    {
        "id": "SU59", "name": "SU59式战斗机", "type": "固定翼",
        "stats": f"HP: {FIGHTER_STATS[2]} | ATK: {60} | RNG: {FIGHTER_STATS[0]} |SPD:{FIGHTER_STATS[1]} ",
        "desc": "作为新时代的作战单位,战斗机的重要性极大的体现在取得空中优势中",
        "history": "",
        "img":"SU57.png","faction":"RUSSIA",
    },

    {
        "id": "FA18E", "name": "FA18E超级大黄蜂式战斗轰炸机", "type": "固定翼",
        "stats": f"HP: {ATTACKER_STATS[2]} | ATK: {400*2} | RNG: {AA_TURRET_STATS[0]} |SPD:{ATTACKER_STATS[1]} ",
        "desc": "攻击机在二战后极速发展,用于对空中力量薄弱的区域进行致命打击",
        "history": "",
        "img":"FA18E.png","faction":"USA",
    },

    {
        "id": "JH7", "name": "JH7-B飞豹式攻击机", "type": "固定翼",
        "stats": f"HP: {ATTACKER_STATS[2]} | ATK: {400*2} | RNG: {AA_TURRET_STATS[0]} |SPD:{ATTACKER_STATS[1]} ",
        "desc": "攻击机在二战后极速发展,用于对空中力量薄弱的区域进行致命打击",
        "history": "歼轰7飞豹战斗轰炸机，为我国海空联合研制生产的一型战斗轰炸机，空军在后续的研发中选择了退出，恰逢特殊情况飞豹项目先后经过多次下马危机，最后好歹成功试飞量产，2000年开始服役，主要执行巡逻和打击任务,在2030年进行了推进力改进后,JH7B仍然作为最先进的超音速攻击机之一活跃在战场上",
        "img":"JH7.png","faction":"CHINA",
    },

    {
        "id": "SU25M", "name": "SU25-M蛙足式攻击机", "type": "固定翼",
        "stats": f"HP: {ATTACKER_STATS[2]} | ATK: {400*2} | RNG: {AA_TURRET_STATS[0]} |SPD:{ATTACKER_STATS[1]} ",
        "desc": "攻击机在二战后极速发展,用于对空中力量薄弱的区域进行致命打击",
        "history": "",
        "img":"SU25M.png","faction":"RUSSIA",
    },

    {
        "id": "mech", "name": "多用途机甲", "type": "地面载具",
        "stats": f"HP: {MECH_STATS[2]} | ATK: {15,60} | RNG: {MECH_STATS[0]} |SPD:{MECH_STATS[1]} ",
        "desc": "在复杂的作战地形中,机甲依旧可以保持其行动力和火力支援",
        "history": "",
        "img":"icon_mech.png","faction":"ALL",
    },

    {
        "id": "harvester", "name": "W-7多功能采矿车", "type": "地面载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "这种矿车是为了应对火星的复杂的矿石区地形而设计的,而其在传统采矿工作的执行中也毫不逊色",
        "history": "",
        "img":"icon_harvester.png","faction":"ALL",
    },

    {
        "id": "wz-10", "name": "WZ-20攻击直升机", "type": "空中载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "wz系列攻击直升机因其出色的低空飞行能力和较高的机动性在20年前开始被越来越多的国家采用,直至今天",
        "history": "",
        "img":"icon_wz10.png","faction":"ALL",
    },

    {
        "id": "missileboat", "name": "护卫舰", "type": "海上载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "护卫舰灵活,轻快,可以对短射程的单位进行有效打击",
        "history": "",
        "img":"icon_missile_boat.png","faction":"ALL",
    },

    {
        "id": "aaboat", "name": "神盾驱逐舰", "type": "海上载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "为了应对空中力量的指数级进化,美国将智能近防系统移植到了驱逐舰上,这个空载毁灭者就此诞生",
        "history": "",
        "img":"icon_antiairfrigate.png","faction":"ALL",
    },

    {
        "id": "missilecruiser", "name": "导弹巡洋舰", "type": "海上载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "优势火力学说在海军中依然适用:一艘巡洋舰能发射的导弹自然是越大越好,越多越好",
        "history": "",
        "img":"icon_missilecruiser.png","faction":"USA,CHINA",
    },

    {
        "id": "laserdestroyer", "name": "聚能潜艇", "type": "海上载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "激光技术一直凭借其在医学上的成就而受到称赞,直到新联邦将钴能源在激发出激光,并将这台毁灭性武器安装在了潜艇上",
        "history": "",
        "img":"icon_.png","faction":"RUSSIA",
    },

    {
        "id": "heavytransport", "name": "饕餮号运输船", "type": "空中载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "这个空中运载者不具备什么攻击性,但它可以运载数千吨的物品在航道上实现运输,或者携带大量重武器发动奇袭",
        "history": "",
        "img":"icon_heavytransport.png","faction":"ALL",
    },

    {
        "id": "bmpt", "name": "终结者型步战车", "type": "地面载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "大多数武器的生产都是为了赢得战争,而终结者的开发则是为了终结战争",
        "history": "",
        "img":"icon_bmpt.png","faction":"RUSSIA",
    },

    {
        "id": "hind", "name": "mi-24超级雌鹿", "type": "空中载具",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "拥有坚硬的护甲和密集的火力,升级多次的mi24已经是名副其实的空中堡垒",
        "history": "",
        "img":"icon_.png","faction":"RUSSIA",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },

    {
        "id": "", "name": "", "type": "",
        "stats": f"HP: {0} | ATK: {0} | RNG: {0} |SPD:{0} ",
        "desc": "",
        "history": "",
        "faction": "",
        "img":"icon_.png","faction":"ALL",
    },



]

# --- 2. 图鉴 UI 类 ---
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
        
        font_path = resource_path(os.path.join("fonts", "simhei.ttf"))
        
        try:
            # 尝试加载本地字体
            self.font_title = pygame.font.Font(font_path, 40)
            self.font_title.set_bold(True) # 手动加粗
            
            self.font_item = pygame.font.Font(font_path, 18)
            
            self.font_detail_h = pygame.font.Font(font_path, 32)
            self.font_detail_h.set_bold(True)
            
            self.font_detail_body = pygame.font.Font(font_path, 20)
            
        except Exception as e:
            print(f"[Warning] Failed to load custom font: {e}")
            # 如果加载失败，回退到默认字体 (None)
            # 虽然丑一点，但绝对不会崩
            self.font_title = pygame.font.Font(None, 40)
            self.font_item = pygame.font.Font(None, 18)
            self.font_detail_h = pygame.font.Font(None, 32)
            self.font_detail_body = pygame.font.Font(None, 20)
        # 筛选状态
        self.filter_faction = "ALL"
        self.filter_type = "ALL"
        
        # 缓存筛选结果 (初始化为全部)
        self.visible_data = DIC_DATA 
        self.btn_back = pygame.Rect(self.margin, SCREEN_HEIGHT - 45, 100, 30)
        
        # 主界面入口按钮 (小书本图标)
        self.btn_open = pygame.Rect(70, 30, 40, 40)
        self.img_cache = {} # [新增] 图片缓存
        self.list_rect = pygame.Rect(self.margin, 150, self.list_w, SCREEN_HEIGHT - 200)
        
        self.btn_faction = pygame.Rect(self.margin, 100, 140, 30)
        self.btn_type = pygame.Rect(self.margin + 150, 100, 140, 30)            
    def apply_filter(self):
        self.visible_data = []
        for item in DIC_DATA:
            # 1. 阵营筛选
            # 假设数据里有 "faction": "USA" 字段，或者是通用的
            # 如果 item 没有 faction 字段，假设它是通用的 (ALL)
            item_fac = item.get("faction", "ALL")
            if self.filter_faction != "ALL":
                # 如果单位是通用的，或者阵营匹配，就保留
                if item_fac != "ALL" and item_fac != self.filter_faction:
                    continue
            
            # 2. 类型筛选
            # 假设数据里有 "type": "Infantry" (在 DIC_DATA 定义里有)
            # 注意大小写，建议统一转大写比较
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
        if not img_name: return None
        if img_name in self.img_cache: return self.img_cache[img_name]
        
        path = resource_path(f"picture/{img_name}")
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                # 统一缩放到 300x200 (或者保持比例)
                img = pygame.transform.scale(img, (300, 200))
                self.img_cache[img_name] = img
                return img
            except: pass
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
                    self.game.state = "DIC" # 切换游戏状态，暂停其他逻辑
                    return True
            return False

        # 2. 图鉴界面交互
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
                
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # 左键
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
            elif event.button == 4: # Up
                self.scroll_y = max(0, self.scroll_y - 30)
            elif event.button == 5: # Down
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
                opts = ["ALL", "地面步兵", "地面载具", "空中载具", "固定翼", "海上载具","生产建筑","防御建筑","多功能","支援"]
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
        self.game.state = "LOGIN" # 返回主菜单

    def draw(self, screen):
        # 1. 绘制入口按钮 (如果未激活)
        if not self.active:
            # 只在 MENU 状态显示
            if self.game.state == "LOGIN":
                pygame.draw.rect(screen, (70, 60, 70), self.btn_open, border_radius=5)
                pygame.draw.rect(screen, WHITE, self.btn_open, 2, border_radius=5)

            return

        # 2. 绘制图鉴界面
        screen.fill((30, 32, 35)) # 深色背景
        
        # 标题
        title = self.font_title.render("UNIT DATABASE", True, YELLOW)
        screen.blit(title, (self.margin, 30))
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
        list_surf = pygame.Surface((self.list_w, max(1, list_h))) # 防止0高度
        list_surf.fill((40, 42, 45))
        
        for i, item in enumerate(self.visible_data):
            rect = pygame.Rect(0, i * self.item_height, self.list_w, self.item_height)
            
            # 选中高亮
            color = (60, 70, 80) if i == self.selected_idx else (40, 42, 45)
            # 鼠标悬停高亮
            # (需要转换鼠标坐标到 list_surf 坐标系，略繁琐，这里简化)
            
            pygame.draw.rect(list_surf, color, rect)
            pygame.draw.rect(list_surf, (80, 80, 90), rect, 1) # 分割线
            
            # 名字
            txt = self.font_item.render(item['name'], True, WHITE)
            list_surf.blit(txt, (10, i * self.item_height + 10))
            
            # 类型标签 (右对齐)
            type_txt = self.font_item.render(item['type'], True, (150, 150, 150))
            list_surf.blit(type_txt, (self.list_w - type_txt.get_width() - 10, i * self.item_height + 10))

        # 裁剪并绘制到屏幕
        sub_rect = pygame.Rect(0, self.scroll_y, self.list_w, self.list_rect.height)
        # 防止 sub_rect 超出 list_surf
        if sub_rect.bottom > list_h: sub_rect.height = list_h - sub_rect.top
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
            
            # 1. 名字与类型
            name_s = self.font_title.render(data['name'], True, WHITE)
            screen.blit(name_s, (self.detail_x, 100))
            if(data.get("faction")):
                faction_s = self.font_item.render(f"Faction:{data['faction']}", True, RED)
                screen.blit(faction_s, (self.detail_x+300, 150))            
            type_s = self.font_item.render(f"Type: {data['type']}", True, CYAN)
            screen.blit(type_s, (self.detail_x, 150))
            
            # 2. 数值面板
            stats_bg = pygame.Rect(self.detail_x, 190, self.detail_w, 40)
            pygame.draw.rect(screen, (50, 50, 60), stats_bg, border_radius=5)
            stat_s = self.font_item.render(data['stats'], True, YELLOW)
            screen.blit(stat_s, (self.detail_x + 10, 200))
            
            # 3. 图片展示
            img_rect = pygame.Rect(self.detail_x, 250, 300, 200)
            
            # [修改] 尝试加载图片
            img_name = data.get("img")
            img_surf = self.get_image(img_name)
            
            if img_surf:
                screen.blit(img_surf, img_rect)
                pygame.draw.rect(screen, WHITE, img_rect, 2) # 边框
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
                current_line = char # 新行从当前字开始
            else:
                current_line = test_line
        
        # 绘制最后一行
        if current_line:
            surf = font.render(current_line, True, color)
            surface.blit(surf, (x, y))
            y += line_height
            
        return y # 返回下一次绘制的Y坐标