"""Jarvis 板块标签 ↔ 东财行业名；全市场估值族映射。"""
from __future__ import annotations

import re

SECTOR_MAP: dict[str, str] = {
    "002463": "PCB",
    "002916": "PCB",
    "300502": "CPO/光模块",
    "300408": "MLCC",
    "002156": "先进封装",
    "600584": "先进封装",
    "300604": "半导体设备",
    "002371": "半导体设备",
    "002409": "半导体材料",
    "301308": "存储",
    "603986": "存储",
    "300480": "半导体",
    "300394": "CPO/光模块",
    "000636": "MLCC",
    "300308": "CPO/光模块",
    "688256": "AI芯片",
    "688041": "AI芯片",
    "688981": "半导体制造",
    "603629": "算力租赁",
    "000815": "算力租赁",
    "300442": "IDC",
    "301396": "算力租赁",
    "600536": "信创",
    "515050": "通信",
    "513310": "半导体",
    "562500": "机器人",
    "562590": "半导体",
    "159300": "宽基",
    "588000": "宽基",
    "159659": "海外",
    "513090": "券商",
    "159740": "港股科技",
    "513330": "港股互联网",
    "515220": "煤炭/红利",
    "159330": "宽基",
    "000333": "消费",
    "002230": "AI/软件",
    "600588": "AI/软件",
    "000899": "电力",
    "000923": "资源",
    "000657": "资源",
    "300033": "金融科技",
    "002131": "其他",
}

SECTOR_FOCUS_ALIASES: dict[str, list[str]] = {
    "PCB": ["印制电路", "PCB", "电子元件", "元件"],
    "CPO/光模块": ["光模块", "通信设备", "通信", "光学光电子", "消费电子"],
    "MLCC": ["电子元件", "元件", "被动元件"],
    "先进封装": ["半导体", "封装测试", "电子"],
    "半导体设备": ["半导体", "专用设备", "半导体设备"],
    "半导体材料": ["半导体", "电子化学品", "材料"],
    "存储": ["半导体", "存储", "电子"],
    "半导体": ["半导体", "电子"],
    "AI芯片": ["半导体", "芯片", "电子", "软件开发", "计算机"],
    "半导体制造": ["半导体", "芯片", "集成电路"],
    "算力租赁": ["互联网服务", "软件开发", "计算机", "通信服务"],
    "IDC": ["互联网服务", "通信服务", "计算机"],
    "信创": ["软件开发", "计算机应用", "计算机设备"],
    "通信": ["通信设备", "通信服务", "通信"],
    "机器人": ["专用设备", "自动化设备", "通用设备", "机械设备"],
    "宽基": [],
    "海外": [],
    "券商": ["证券"],
    "港股科技": ["互联网服务", "软件开发", "通信"],
    "港股互联网": ["互联网服务", "软件开发"],
    "煤炭/红利": ["煤炭行业", "煤炭", "采掘"],
    "消费": ["白酒", "食品饮料", "家电", "商业贸易", "消费"],
    "AI/软件": ["软件开发", "计算机应用", "互联网服务", "软件"],
    "电力": ["电力行业", "电力"],
    "资源": ["有色金属", "钢铁行业", "能源金属", "工业金属", "小金属"],
    "金融科技": ["软件开发", "计算机应用", "多元金融"],
    "其他": [],
}


def raw_code(code: str) -> str:
    return re.sub(r"^(sh|sz)", "", str(code or ""), flags=re.I)


def get_sector(code: str) -> str:
    return SECTOR_MAP.get(raw_code(code), "其他")


# 板块标签 → 估值族（合理 PE 区间不同）；自选细分类优先于此表
SECTOR_VALUATION_GROUP: dict[str, str] = {
    # 科技/成长
    "PCB": "tech",
    "CPO/光模块": "tech",
    "MLCC": "tech",
    "先进封装": "tech",
    "半导体设备": "tech",
    "半导体材料": "tech",
    "存储": "tech",
    "半导体": "tech",
    "AI芯片": "tech",
    "半导体制造": "tech",
    "算力租赁": "tech",
    "IDC": "tech",
    "信创": "tech",
    "通信": "tech",
    "机器人": "tech",
    "AI/软件": "tech",
    "金融科技": "tech",
    "港股科技": "tech",
    "港股互联网": "tech",
    # 消费品牌（允许溢价）
    "消费": "consumer",
    # 周期 / 红利
    "资源": "cyclical",
    "煤炭/红利": "cyclical",
    # 公用事业
    "电力": "utility",
    # 金融
    "券商": "finance",
    # 指数 / ETF（PE 参考意义弱）
    "宽基": "etf",
    "海外": "etf",
    "其他": "default",
}

# 东财/申万常见行业名关键词 → 估值族（全市场；先匹配更长词）
# 新自选若不在 SECTOR_MAP，靠 industry/hybk 文本落入对应族，避免一律 default。
INDUSTRY_GROUP_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "tech",
        (
            "半导体",
            "集成电路",
            "芯片",
            "电子元件",
            "元件",
            "消费电子",
            "光学光电子",
            "其他电子",
            "电子化学品",
            "印制电路",
            "PCB",
            "软件开发",
            "计算机应用",
            "计算机设备",
            "互联网服务",
            "通信设备",
            "通信服务",
            "数字媒体",
            "广告营销",
            "影视院线",
            "电视广播",
            "游戏",
            "出版",
            "云服务",
            "数据中心",
            "IT服务",
            "电池",
            "光伏设备",
            "风电设备",
            "电网设备",
            "电机",
            "其他电源设备",
            "军工电子",
            "电子",
            "计算机",
            "软件",
            "通信",
            "传媒",
            "电力设备",
            "自动化设备",
            "机器人",
        ),
    ),
    (
        "healthcare",
        (
            "生物制品",
            "化学制药",
            "中药",
            "医药商业",
            "医疗器械",
            "医疗服务",
            "医药生物",
            "创新药",
            "疫苗",
            "CXO",
            "医药",
        ),
    ),
    (
        "consumer",
        (
            "白酒",
            "啤酒",
            "饮料制造",
            "调味发酵品",
            "食品加工",
            "食品饮料",
            "白色家电",
            "黑色家电",
            "小家电",
            "家电零部件",
            "家电",
            "纺织制造",
            "服装家纺",
            "饰品",
            "家居用品",
            "商贸零售",
            "一般零售",
            "专业连锁",
            "旅游零售",
            "互联网电商",
            "酒店餐饮",
            "旅游景区",
            "教育",
            "体育",
            "美容护理",
            "社会服务",
            "包装印刷",
            "造纸",
            "消费",
        ),
    ),
    (
        "finance",
        (
            "银行",
            "证券",
            "保险",
            "多元金融",
            "信托",
            "期货",
            "租赁",
            "金融",
            "券商",
        ),
    ),
    (
        "utility",
        (
            "火力发电",
            "水力发电",
            "光伏发电",
            "风力发电",
            "核力发电",
            "电力行业",
            "燃气",
            "水务",
            "环境治理",
            "环保",
            "公用事业",
            "电力",
        ),
    ),
    (
        "cyclical",
        (
            "煤炭开采",
            "焦炭",
            "煤炭",
            "油气开采",
            "油服工程",
            "炼化及贸易",
            "石油加工",
            "石油石化",
            "化学原料",
            "化学制品",
            "化学纤维",
            "塑料",
            "橡胶",
            "农化制品",
            "基础化工",
            "冶钢原料",
            "普钢",
            "特钢",
            "钢铁",
            "工业金属",
            "能源金属",
            "贵金属",
            "小金属",
            "金属新材料",
            "有色金属",
            "采掘",
            "水泥",
            "玻璃玻纤",
            "装修建材",
            "建筑材料",
            "房地产开发",
            "房地产服务",
            "房地产",
            "航运港口",
            "航空机场",
            "铁路公路",
            "物流",
            "交通运输",
            "能源",
            "资源",
        ),
    ),
    (
        "manufacturing",
        (
            "专用设备",
            "通用设备",
            "工程机械",
            "仪器仪表",
            "金属制品",
            "轨交设备",
            "机械设备",
            "汽车整车",
            "汽车零部件",
            "摩托车及其他",
            "汽车服务",
            "汽车",
            "航天装备",
            "航空装备",
            "地面兵装",
            "船舶制造",
            "国防军工",
            "农牧饲渔",
            "农产品加工",
            "养殖业",
            "种植业",
            "动物保健",
            "农林牧渔",
            "装修装饰",
            "房屋建设",
            "基础建设",
            "专业工程",
            "工程咨询服务",
            "建筑装饰",
            "综合",
        ),
    ),
    (
        "etf",
        ("ETF", "LOF", "宽基", "指数基金"),
    ),
]

# hard_max: 超此剔除；loss_pts: PE≤0 综合分；bands: (pe上界, 分)
# soft_*: 策略软分比例
VALUATION_PROFILES: dict[str, dict] = {
    "tech": {
        "label": "科技成长",
        "hard_max": 300.0,
        "loss_pts": 10,
        "bands": ((50, 25), (100, 20), (180, 15), (300, 10)),
        "soft_loss": 0.4,
        "soft_bands": ((60, 1.0), (120, 0.75), (200, 0.5), (300, 0.3)),
    },
    "healthcare": {
        "label": "医药生物",
        "hard_max": 250.0,
        "loss_pts": 8,
        "bands": ((40, 25), (80, 20), (150, 15), (250, 10)),
        "soft_loss": 0.35,
        "soft_bands": ((50, 1.0), (100, 0.75), (180, 0.5), (250, 0.3)),
    },
    "consumer": {
        "label": "消费品牌",
        "hard_max": 200.0,
        "loss_pts": 0,
        "bands": ((25, 25), (40, 22), (60, 18), (100, 12), (200, 8)),
        "soft_loss": 0.0,
        "soft_bands": ((35, 1.0), (55, 0.75), (100, 0.5), (200, 0.3)),
    },
    "manufacturing": {
        "label": "制造/军工",
        "hard_max": 120.0,
        "loss_pts": 0,
        "bands": ((20, 25), (35, 20), (60, 15), (120, 8)),
        "soft_loss": 0.0,
        "soft_bands": ((25, 1.0), (45, 0.7), (80, 0.4), (120, 0.25)),
    },
    "cyclical": {
        "label": "周期资源",
        "hard_max": 80.0,
        "loss_pts": 0,
        "bands": ((12, 25), (20, 20), (35, 15), (80, 8)),
        "soft_loss": 0.0,
        "soft_bands": ((15, 1.0), (25, 0.7), (50, 0.4), (80, 0.25)),
    },
    "utility": {
        "label": "公用事业",
        "hard_max": 100.0,
        "loss_pts": 0,
        "bands": ((15, 25), (25, 20), (40, 15), (100, 8)),
        "soft_loss": 0.0,
        "soft_bands": ((18, 1.0), (30, 0.7), (50, 0.4), (100, 0.25)),
    },
    "finance": {
        "label": "金融",
        "hard_max": 80.0,
        "loss_pts": 0,
        "bands": ((10, 25), (18, 20), (30, 15), (80, 8)),
        "soft_loss": 0.0,
        "soft_bands": ((12, 1.0), (20, 0.7), (40, 0.4), (80, 0.25)),
    },
    "etf": {
        "label": "宽基/ETF",
        "hard_max": 500.0,
        "loss_pts": 12,
        "bands": ((20, 22), (40, 18), (80, 14), (500, 10)),
        "soft_loss": 0.5,
        "soft_bands": ((30, 0.9), (60, 0.7), (120, 0.5), (500, 0.35)),
    },
    "default": {
        "label": "通用",
        "hard_max": 150.0,
        "loss_pts": 0,
        "bands": ((30, 25), (50, 20), (80, 15), (150, 10)),
        "soft_loss": 0.0,
        "soft_bands": ((40, 1.0), (70, 0.7), (150, 0.4)),
    },
}


def resolve_sector_label(code_or_sector: str | None = None, *, sector: str | None = None) -> str:
    label = (sector or "").strip()
    if label:
        return label
    if not code_or_sector:
        return "其他"
    s = str(code_or_sector).strip()
    if s in SECTOR_VALUATION_GROUP or s in SECTOR_MAP.values():
        return s
    return get_sector(s)


def match_valuation_group_from_text(text: str | None) -> str | None:
    """用东财行业名 / 板块名关键词推断估值族。"""
    t = str(text or "").strip()
    if not t or t == "其他":
        return None
    if t in SECTOR_VALUATION_GROUP and t != "其他":
        return SECTOR_VALUATION_GROUP[t]
    best: tuple[int, str] | None = None
    for group, kws in INDUSTRY_GROUP_RULES:
        for kw in kws:
            if kw and kw in t:
                n = len(kw)
                if best is None or n > best[0]:
                    best = (n, group)
    return best[1] if best else None


def _etf_group_from_code(code: str) -> str | None:
    c = raw_code(code)
    if len(c) != 6 or not c.isdigit():
        return None
    # 常见场内基金前缀（避免误伤 000/002/300/600 等 A 股）
    if c.startswith(("51", "56", "58", "15", "16", "18")):
        return "etf"
    return None


def valuation_group(
    code_or_sector: str | None = None,
    *,
    sector: str | None = None,
    industry: str | None = None,
) -> str:
    """
    解析顺序：
    1. Jarvis 自选细分类（SECTOR_MAP / 显式 sector，且非「其他」）
    2. 东财行业名 / hybk / 板块文本关键词（全市场）
    3. 代码形态（ETF、科创板偏成长）
    4. default
    """
    label = resolve_sector_label(code_or_sector, sector=sector)
    if label and label != "其他" and label in SECTOR_VALUATION_GROUP:
        return SECTOR_VALUATION_GROUP[label]

    for text in (industry, sector, label):
        g = match_valuation_group_from_text(text)
        if g:
            return g

    code = raw_code(code_or_sector or "")
    eg = _etf_group_from_code(code)
    if eg:
        return eg
    if code.startswith("688"):
        return "tech"
    return "default"


def valuation_profile(group: str | None = None) -> dict:
    g = group or "default"
    return VALUATION_PROFILES.get(g) or VALUATION_PROFILES["default"]


# 兼容旧名
TECH_SECTOR_LABELS = frozenset(k for k, v in SECTOR_VALUATION_GROUP.items() if v == "tech")


def is_tech_sector(
    code_or_sector: str | None = None,
    *,
    sector: str | None = None,
    industry: str | None = None,
) -> bool:
    return valuation_group(code_or_sector, sector=sector, industry=industry) == "tech"


def sector_focus_keywords(item_sector: str) -> list[str]:
    a = str(item_sector or "").strip()
    if not a or a == "其他":
        return []
    aliases = SECTOR_FOCUS_ALIASES.get(a) or []
    tokens = [t for t in re.split(r"[/·、\s]+", a) if len(t) >= 2]
    out: list[str] = []
    for k in [a, *tokens, *aliases]:
        if k and k not in out:
            out.append(k)
    return out


def sector_match(item_sector: str, east_name: str) -> bool:
    a = str(item_sector or "").strip()
    b = str(east_name or "").strip()
    if not a or not b or a == "其他":
        return False
    if a in b or b in a:
        return True
    return any(len(k) >= 2 and (k in b or b in k) for k in sector_focus_keywords(a))


def match_focus_sector(code: str, focus_names: list[str]) -> str | None:
    sec = get_sector(code)
    for name in focus_names:
        if sector_match(sec, name):
            return name
    return None
