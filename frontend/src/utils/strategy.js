export const SECTOR_MAP = {
  '002463': 'PCB', '002916': 'PCB', '300502': 'CPO/光模块', '300408': 'MLCC', '002156': '先进封装',
  '600584': '先进封装', '300604': '半导体设备', '002371': '半导体设备', '002409': '半导体材料',
  '301308': '存储', '603986': '存储', '300480': '半导体', '300394': 'CPO/光模块', '000636': 'MLCC',
  '300308': 'CPO/光模块', '688256': 'AI芯片', '688041': 'AI芯片', '688981': '半导体制造',
  '603629': '算力租赁', '000815': '算力租赁', '300442': 'IDC', '301396': '算力租赁', '600536': '信创',
  '515050': '通信', '513310': '半导体', '562500': '机器人', '562590': '半导体', '159300': '宽基',
  '588000': '宽基', '159659': '海外', '513090': '券商', '159740': '港股科技', '513330': '港股互联网',
  '515220': '煤炭/红利', '159330': '宽基', '000333': '消费', '002230': 'AI/软件', '600588': 'AI/软件',
  '000899': '电力', '000923': '资源', '000657': '资源', '300033': '金融科技', '002131': '其他',
}

/**
 * 自家板块标签 → 东财行业板块关键词（资金流 m:90 t:2）。
 * 用于「主线重合」判定，避免 PCB 对不上「电子元件」这类假阴性。
 */
export const SECTOR_FOCUS_ALIASES = {
  PCB: ['印制电路', 'PCB', '电子元件', '元件'],
  'CPO/光模块': ['光模块', '通信设备', '通信', '光学光电子', '消费电子'],
  MLCC: ['电子元件', '元件', '被动元件'],
  先进封装: ['半导体', '封装测试', '电子'],
  半导体设备: ['半导体', '专用设备', '半导体设备'],
  半导体材料: ['半导体', '电子化学品', '材料'],
  存储: ['半导体', '存储', '电子'],
  半导体: ['半导体', '电子'],
  AI芯片: ['半导体', '芯片', '电子', '软件开发', '计算机'],
  半导体制造: ['半导体', '芯片', '集成电路'],
  算力租赁: ['互联网服务', '软件开发', '计算机', '通信服务'],
  IDC: ['互联网服务', '通信服务', '计算机'],
  信创: ['软件开发', '计算机应用', '计算机设备'],
  通信: ['通信设备', '通信服务', '通信'],
  机器人: ['专用设备', '自动化设备', '通用设备', '机械设备'],
  宽基: [],
  海外: [],
  券商: ['证券'],
  港股科技: ['互联网服务', '软件开发', '通信'],
  港股互联网: ['互联网服务', '软件开发'],
  '煤炭/红利': ['煤炭行业', '煤炭', '采掘'],
  消费: ['白酒', '食品饮料', '家电', '商业贸易', '消费'],
  'AI/软件': ['软件开发', '计算机应用', '互联网服务', '软件'],
  电力: ['电力行业', '电力'],
  资源: ['有色金属', '钢铁行业', '能源金属', '工业金属', '小金属'],
  金融科技: ['软件开发', '计算机应用', '多元金融'],
  其他: [],
}

export function getSector(code) {
  const raw = String(code || '').replace(/^(sh|sz)/i, '')
  return SECTOR_MAP[raw] || '其他'
}

/** 自家板块是否可能对应某东财行业名 */
export function sectorFocusKeywords(itemSector) {
  const a = String(itemSector || '').trim()
  if (!a || a === '其他') return []
  const aliases = SECTOR_FOCUS_ALIASES[a] || []
  const tokens = a.split(/[\/·、\s]+/).filter((t) => t.length >= 2)
  return [...new Set([a, ...tokens, ...aliases].filter(Boolean))]
}

export const ANALYSIS_STALE_DAYS = 14

/** 板块标签 → 估值族（自选细分类优先） */
export const SECTOR_VALUATION_GROUP = {
  PCB: 'tech', 'CPO/光模块': 'tech', MLCC: 'tech', 先进封装: 'tech',
  半导体设备: 'tech', 半导体材料: 'tech', 存储: 'tech', 半导体: 'tech',
  AI芯片: 'tech', 半导体制造: 'tech', 算力租赁: 'tech', IDC: 'tech', 信创: 'tech',
  通信: 'tech', 机器人: 'tech', 'AI/软件': 'tech', 金融科技: 'tech',
  港股科技: 'tech', 港股互联网: 'tech',
  消费: 'consumer',
  资源: 'cyclical', '煤炭/红利': 'cyclical',
  电力: 'utility',
  券商: 'finance',
  宽基: 'etf', 海外: 'etf',
  其他: 'default',
}

/**
 * 东财/申万常见行业关键词 → 估值族（全市场）。
 * 与 backend/app/domain/sectors.py INDUSTRY_GROUP_RULES 对齐。
 */
export const INDUSTRY_GROUP_RULES = [
  ['tech', [
    '半导体', '集成电路', '芯片', '电子元件', '元件', '消费电子', '光学光电子', '其他电子', '电子化学品',
    '印制电路', 'PCB', '软件开发', '计算机应用', '计算机设备', '互联网服务', '通信设备', '通信服务',
    '数字媒体', '广告营销', '影视院线', '电视广播', '游戏', '出版', '云服务', '数据中心', 'IT服务',
    '电池', '光伏设备', '风电设备', '电网设备', '电机', '其他电源设备', '军工电子',
    '电子', '计算机', '软件', '通信', '传媒', '电力设备', '自动化设备', '机器人',
  ]],
  ['healthcare', [
    '生物制品', '化学制药', '中药', '医药商业', '医疗器械', '医疗服务', '医药生物', '创新药', '疫苗', 'CXO', '医药',
  ]],
  ['consumer', [
    '白酒', '啤酒', '饮料制造', '调味发酵品', '食品加工', '食品饮料',
    '白色家电', '黑色家电', '小家电', '家电零部件', '家电',
    '纺织制造', '服装家纺', '饰品', '家居用品',
    '商贸零售', '一般零售', '专业连锁', '旅游零售', '互联网电商',
    '酒店餐饮', '旅游景区', '教育', '体育', '美容护理', '社会服务',
    '包装印刷', '造纸', '消费',
  ]],
  ['finance', ['银行', '证券', '保险', '多元金融', '信托', '期货', '租赁', '金融', '券商']],
  ['utility', [
    '火力发电', '水力发电', '光伏发电', '风力发电', '核力发电', '电力行业',
    '燃气', '水务', '环境治理', '环保', '公用事业', '电力',
  ]],
  ['cyclical', [
    '煤炭开采', '焦炭', '煤炭', '油气开采', '油服工程', '炼化及贸易', '石油加工', '石油石化',
    '化学原料', '化学制品', '化学纤维', '塑料', '橡胶', '农化制品', '基础化工',
    '冶钢原料', '普钢', '特钢', '钢铁', '工业金属', '能源金属', '贵金属', '小金属', '金属新材料', '有色金属', '采掘',
    '水泥', '玻璃玻纤', '装修建材', '建筑材料',
    '房地产开发', '房地产服务', '房地产',
    '航运港口', '航空机场', '铁路公路', '物流', '交通运输', '能源', '资源',
  ]],
  ['manufacturing', [
    '专用设备', '通用设备', '工程机械', '仪器仪表', '金属制品', '轨交设备', '机械设备',
    '汽车整车', '汽车零部件', '摩托车及其他', '汽车服务', '汽车',
    '航天装备', '航空装备', '地面兵装', '船舶制造', '国防军工',
    '农牧饲渔', '农产品加工', '养殖业', '种植业', '动物保健', '农林牧渔',
    '装修装饰', '房屋建设', '基础建设', '专业工程', '工程咨询服务', '建筑装饰', '综合',
  ]],
  ['etf', ['ETF', 'LOF', '宽基', '指数基金']],
]

/** hard_max / loss_pts / bands / soft_* —— 与 backend domain/sectors 对齐 */
export const VALUATION_PROFILES = {
  tech: {
    label: '科技成长', hardMax: 300, lossPts: 10,
    bands: [[50, 25], [100, 20], [180, 15], [300, 10]],
    softLoss: 0.4, softBands: [[60, 1], [120, 0.75], [200, 0.5], [300, 0.3]],
  },
  healthcare: {
    label: '医药生物', hardMax: 250, lossPts: 8,
    bands: [[40, 25], [80, 20], [150, 15], [250, 10]],
    softLoss: 0.35, softBands: [[50, 1], [100, 0.75], [180, 0.5], [250, 0.3]],
  },
  consumer: {
    label: '消费品牌', hardMax: 200, lossPts: 0,
    bands: [[25, 25], [40, 22], [60, 18], [100, 12], [200, 8]],
    softLoss: 0, softBands: [[35, 1], [55, 0.75], [100, 0.5], [200, 0.3]],
  },
  manufacturing: {
    label: '制造/军工', hardMax: 120, lossPts: 0,
    bands: [[20, 25], [35, 20], [60, 15], [120, 8]],
    softLoss: 0, softBands: [[25, 1], [45, 0.7], [80, 0.4], [120, 0.25]],
  },
  cyclical: {
    label: '周期资源', hardMax: 80, lossPts: 0,
    bands: [[12, 25], [20, 20], [35, 15], [80, 8]],
    softLoss: 0, softBands: [[15, 1], [25, 0.7], [50, 0.4], [80, 0.25]],
  },
  utility: {
    label: '公用事业', hardMax: 100, lossPts: 0,
    bands: [[15, 25], [25, 20], [40, 15], [100, 8]],
    softLoss: 0, softBands: [[18, 1], [30, 0.7], [50, 0.4], [100, 0.25]],
  },
  finance: {
    label: '金融', hardMax: 80, lossPts: 0,
    bands: [[10, 25], [18, 20], [30, 15], [80, 8]],
    softLoss: 0, softBands: [[12, 1], [20, 0.7], [40, 0.4], [80, 0.25]],
  },
  etf: {
    label: '宽基/ETF', hardMax: 500, lossPts: 12,
    bands: [[20, 22], [40, 18], [80, 14], [500, 10]],
    softLoss: 0.5, softBands: [[30, 0.9], [60, 0.7], [120, 0.5], [500, 0.35]],
  },
  default: {
    label: '通用', hardMax: 150, lossPts: 0,
    bands: [[30, 25], [50, 20], [80, 15], [150, 10]],
    softLoss: 0, softBands: [[40, 1], [70, 0.7], [150, 0.4]],
  },
}

export function resolveSectorLabel(codeOrSector, sector) {
  const label = String(sector || '').trim()
  if (label) return label
  if (!codeOrSector) return '其他'
  const s = String(codeOrSector).trim()
  if (SECTOR_VALUATION_GROUP[s] || Object.values(SECTOR_MAP).includes(s)) return s
  return getSector(s)
}

export function matchValuationGroupFromText(text) {
  const t = String(text || '').trim()
  if (!t || t === '其他') return null
  if (SECTOR_VALUATION_GROUP[t] && t !== '其他') return SECTOR_VALUATION_GROUP[t]
  let bestLen = 0
  let bestGroup = null
  for (const [group, kws] of INDUSTRY_GROUP_RULES) {
    for (const kw of kws) {
      if (kw && t.includes(kw) && kw.length > bestLen) {
        bestLen = kw.length
        bestGroup = group
      }
    }
  }
  return bestGroup
}

function etfGroupFromCode(code) {
  const c = String(code || '').replace(/^(sh|sz)/i, '')
  if (c.length !== 6 || !/^\d+$/.test(c)) return null
  if (/^(51|56|58|15|16|18)/.test(c)) return 'etf'
  return null
}

/**
 * 解析顺序：自选细分类 → 东财行业关键词 → ETF/科创板启发式 → default
 * @param {string} [codeOrSector]
 * @param {string} [sector]
 * @param {string} [industry] 东财行业名 / hybk
 */
export function valuationGroup(codeOrSector, sector, industry) {
  const label = resolveSectorLabel(codeOrSector, sector)
  if (label && label !== '其他' && SECTOR_VALUATION_GROUP[label]) {
    return SECTOR_VALUATION_GROUP[label]
  }
  for (const text of [industry, sector, label]) {
    const g = matchValuationGroupFromText(text)
    if (g) return g
  }
  const code = String(codeOrSector || '').replace(/^(sh|sz)/i, '')
  const eg = etfGroupFromCode(code)
  if (eg) return eg
  if (code.startsWith('688')) return 'tech'
  return 'default'
}

export function valuationProfile(group) {
  return VALUATION_PROFILES[group] || VALUATION_PROFILES.default
}

/** @deprecated 用 valuationGroup === 'tech' */
export const TECH_SECTOR_LABELS = new Set(
  Object.entries(SECTOR_VALUATION_GROUP).filter(([, g]) => g === 'tech').map(([k]) => k),
)

export function isTechSector(codeOrSector, sector, industry) {
  return valuationGroup(codeOrSector, sector, industry) === 'tech'
}

export function peHardMax(groupOrTech = 'default') {
  if (typeof groupOrTech === 'boolean') {
    return valuationProfile(groupOrTech ? 'tech' : 'default').hardMax
  }
  return valuationProfile(groupOrTech || 'default').hardMax
}

/** 兼容旧常量 */
export const PE_HARD_MAX = 150
export const PE_HARD_MAX_TECH = 300

/**
 * 综合分 PE 项（满分 25）。opts.group 或 opts.tech / code+sector 自动推断。
 */
export function peCompositePoints(pe, opts = {}) {
  const group = opts.group
    || (opts.tech != null ? (opts.tech ? 'tech' : 'default') : null)
    || valuationGroup(opts.code, opts.sector, opts.industry)
  const p = valuationProfile(group)
  const n = Number(pe) || 0
  if (!(n > 0)) return p.lossPts || 0
  for (const [upper, pts] of p.bands) {
    if (n < upper) return pts
  }
  return 0
}

export function liveScoreFrom(q, k, opts = {}) {
  if (!q || q.price <= 0 || !k || (k.ma20 <= 0 && typeof k.change20d !== 'number')) return null
  let s = 0
  const pe = q.peTTM > 0 ? q.peTTM : (q.pe > 0 ? q.pe : 0)
  const code = opts.code || q.code
  const industry = opts.industry || q.industry || q.hybk || ''
  const group = opts.group || valuationGroup(code, opts.sector, industry)
  s += peCompositePoints(pe, { group })
  if (k.ma20 > 0) {
    const dist = (q.price - k.ma20) / k.ma20 * 100
    if (dist >= 0) s += 25
    else if (dist > -3) s += 20
    else if (dist > -5) s += 15
    else if (dist > -10) s += 5
  }
  const c20 = k.change20d || 0
  if (c20 > 5) s += 20
  else if (c20 > 0) s += 15
  else if (c20 > -5) s += 10
  else if (c20 > -10) s += 5
  const lb = q.liangbi || 0
  if (lb > 2) s += 15
  else if (lb > 1.5) s += 12
  else if (lb > 1) s += 8
  else s += 5
  const wb = q.weibi || 0
  if (wb > 30) s += 15
  else if (wb > 10) s += 12
  else if (wb > 0) s += 8
  else if (wb > -20) s += 5
  return s
}

/** 五灯·海外冲击（v4.1） */
export const OVERSEAS_SPX_RED = -1.5
export const OVERSEAS_QQQ_RED = -2.0
/** 五灯·生态恶化（v4.1） */
export const ECO_YEST_LOSS_RED = 3
export const ECO_DT_RED = 10
export const ECO_MAX_DAYS_COLD = 2
/** 指数破位：沪深300 / 创业板 连续破 MA60 */
export const INDEX_BREAK_CODES = ['sh000300', 'sz399006']
export const INDEX_BREAK_CONFIRM_DAYS = 3
/** 买入偏离门禁：现价 ≤ MA20×1.05 */
export const BUY_MAX_MA20_DEV = 0.05
/** 铁律1：破线缓冲带与确认日 */
export const MA20_BREAK_BUF = 0.98
export const IRON1_HALF_DAYS = 3
export const IRON1_CLEAR_DAYS = 5


export function ratingFromScore(score) {
  if (score >= 60) return '可买入'
  if (score >= 40) return '观察'
  if (score >= 20) return '不追'
  return '排除'
}

/** 评分着色：A 股习惯红强绿弱，并与评级档对齐 */
export function scoreColor(score) {
  const s = Number(score)
  if (!Number.isFinite(s)) return 'var(--muted)'
  if (s >= 60) return 'var(--red)'      // 可买入
  if (s >= 40) return 'var(--blue)'     // 观察
  if (s >= 20) return 'var(--orange)'   // 不追
  return 'var(--green)'                 // 排除
}

export function ratingClassOf(rating) {
  if (rating === '可买入') return 'buy'
  if (rating === '观察') return 'watch'
  if (rating === '持仓' || rating === '持有') return 'hold'
  if (rating === '不追' || rating === '不买') return 'nochase'
  return 'exclude'
}

export function daysSince(dateStr) {
  if (!dateStr) return Infinity
  const t = new Date(`${String(dateStr).slice(0, 10)}T00:00:00`).getTime()
  if (Number.isNaN(t)) return Infinity
  return Math.floor((Date.now() - t) / 86400000)
}

export function isAnalysisStale(a, staleDays = ANALYSIS_STALE_DAYS) {
  if (!a) return true
  return daysSince(a.reviewedAt) > staleDays
}

export function isRiskCleared(a, staleDays = ANALYSIS_STALE_DAYS) {
  return !!(a && a.riskOk === true && !isAnalysisStale(a, staleDays))
}

export function makeSparkline(prices, w = 200, h = 30) {
  if (!prices || prices.length < 2) return ''
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 1
  const pts = prices.map((p, i) => {
    const x = (i / (prices.length - 1)) * w
    const y = h - ((p - min) / range) * h
    return `${x},${y}`
  }).join(' ')
  const up = prices[prices.length - 1] >= prices[0]
  const color = up ? '#f85149' : '#3fb950'
  const fill = up ? 'rgba(248,81,73,0.1)' : 'rgba(63,185,80,0.1)'
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polygon points="0,${h} ${pts} ${w},${h}" fill="${fill}"/><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5"/></svg>`
}
