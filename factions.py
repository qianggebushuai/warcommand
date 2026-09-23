import random

class Faction:
    def __init__(self, name, color, special_units, base_style):
        self.name = name
        self.color = color
        self.special_units = special_units # 列表: ["type99", ...]
        self.base_style = base_style # "cn", "us", "ru"

# 阵营配置库
FACTIONS_DATA = {
    "CHINA": Faction(
        name="PLA", 
        color=(200, 50, 50), # 鲜红
        special_units=["type99"], 
        base_style="cn"
    ),
    "USA": Faction(
        name="US ARMY", 
        color=(50, 50, 200), # 深蓝
        special_units=["himars"], 
        base_style="us"
    ),
    "RUSSIA": Faction(
        name="RUSSIAN FED", 
        color=(150, 100, 50), # 褐/深绿
        special_units=["mi24"], 
        base_style="ru"
    )
}

def get_random_faction():
    key = random.choice(list(FACTIONS_DATA.keys()))
    return key, FACTIONS_DATA[key]