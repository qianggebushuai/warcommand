from core.settings import *
from core.base_classes import *
from .base import *
from .infantry import *
from .vehicles import *
from .aircraft import *
from .missiles import *
from .ships import *
from .buildings import *
from .defenses import *

# 运行期回注：让各子模块方法体可直接用裸类名引用兄弟单位类（避免顶层循环导入）。
# 在包初始化完成后，把聚合命名空间中的名字补进每个子模块（不覆盖子模块已有名字）。
from . import base as _m_base, infantry as _m_inf, vehicles as _m_veh, aircraft as _m_air, \
    missiles as _m_mis, ships as _m_ship, buildings as _m_bld, defenses as _m_def
for _sub in (_m_base, _m_inf, _m_veh, _m_air, _m_mis, _m_ship, _m_bld, _m_def):
    for _k, _v in list(globals().items()):
        if _k.startswith('_'):
            continue
        if not hasattr(_sub, _k):
            setattr(_sub, _k, _v)
