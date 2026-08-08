import {
  OVERSEAS_QQQ_RED,
  OVERSEAS_SPX_RED,
  ECO_YEST_LOSS_RED,
  ECO_DT_RED,
  ECO_MAX_DAYS_COLD,
  INDEX_BREAK_CODES,
  INDEX_BREAK_CONFIRM_DAYS,
  BUY_MAX_MA20_DEV,
  MA20_BREAK_BUF,
  IRON1_HALF_DAYS,
  IRON1_CLEAR_DAYS,
  getSector,
  isRiskCleared,
  liveScoreFrom,
  ratingFromScore,
  sectorFocusKeywords,
} from './strategy'

const STOP_LOSS_PCT = -8
const PROFIT_TAKE_PCT = 10
const PROFIT_TAKE_L2 = 20
const PROFIT_TAKE_L3 = 30
const PROFIT_GREEN_PCT = 3
const PROFIT_GREEN_CONFIRM_PCT = 1.5
const DRAWDOWN_ALERT_PCT = 3
const DRAWDOWN_ALERT_STRONG = 3.6
const HIGH_60D_PCT = 50
const BIG_DROP_PCT = -5
const TIME_STOP_DAYS = 7
const LEVER_KEY = 'jarvis_lever5_override'
const MAIN_RISE_ICE_KEY = 'jarvis_main_rise_ice'

export { STOP_LOSS_PCT, PROFIT_TAKE_PCT, PROFIT_TAKE_L2, PROFIT_TAKE_L3 }

/** 板块止损阈值（成本 / 跟踪），单位 %（负值） */
export function boardStopPcts(code, name) {
  const raw = String(code || '').replace(/^(sh|sz)/i, '')
  const nm = String(name || '')
  if (/ST/i.test(nm)) return { cost: -5, trail: -5, label: 'ST' }
  if (/^(300|301|688)/.test(raw)) return { cost: -12, trail: -10, label: '创科' }
  return { cost: -8, trail: -8, label: '主板' }
}

/**
 * 持仓止损/止盈参考价。
 * 有自定义价则用自定义；否则按板块成本止损 + 一级止盈自动算。
 * opts: { code, name, maxHigh, strongTrend }
 */
export function positionRiskLevels(pos, price, opts = {}) {
  const buy = Number(pos?.buyPrice) || 0
  if (!(buy > 0)) return null
  const { cost, trail, label } = boardStopPcts(opts.code || pos?.code, opts.name || pos?.name)
  const widen = opts.strongTrend ? 1.2 : 1
  const costPct = cost * widen
  const trailPct = trail * widen
  const customSl = Number(pos?.stopLossPrice)
  const customTp = Number(pos?.takeProfitPrice)
  const hasCustomSl = Number.isFinite(customSl) && customSl > 0
  const hasCustomTp = Number.isFinite(customTp) && customTp > 0
  const autoStopLoss = buy * (1 + costPct / 100)
  const autoTakeProfit = buy * (1 + PROFIT_TAKE_PCT / 100)
  const stopLoss = hasCustomSl ? customSl : autoStopLoss
  const takeProfit = hasCustomTp ? customTp : autoTakeProfit
  const p = Number(price) || 0
  const maxHigh = Number(opts.maxHigh) || 0
  const trailStop = maxHigh > 0 ? maxHigh * (1 + trailPct / 100) : null
  const costHit = p > 0 && p <= stopLoss
  const trailHit = trailStop != null && p > 0 && p <= trailStop && maxHigh > buy
  return {
    stopLoss,
    takeProfit,
    trailStop,
    boardLabel: label,
    costPct,
    trailPct,
    stopLossSource: hasCustomSl ? 'custom' : 'auto',
    takeProfitSource: hasCustomTp ? 'custom' : 'auto',
    autoStopLoss,
    autoTakeProfit,
    distToStopPct: p > 0 ? ((p - stopLoss) / stopLoss) * 100 : null,
    distToTakePct: p > 0 ? ((takeProfit - p) / p) * 100 : null,
    stopHit: costHit || trailHit,
    costHit,
    trailHit,
    takeHit: p > 0 && p >= takeProfit,
  }
}

export function getLeverOverride() {
  return localStorage.getItem(LEVER_KEY) === '1'
}
export function toggleLeverOverride() {
  const on = getLeverOverride()
  localStorage.setItem(LEVER_KEY, on ? '0' : '1')
  return !on
}
export function getMainRiseIce() {
  return localStorage.getItem(MAIN_RISE_ICE_KEY) === '1'
}
export function toggleMainRiseIce() {
  const on = getMainRiseIce()
  localStorage.setItem(MAIN_RISE_ICE_KEY, on ? '0' : '1')
  return !on
}

function isEarningsWindow() {
  const d = new Date()
  const m = d.getMonth() + 1
  const day = d.getDate()
  // v4.1：1/17–1/31、7/1–7/15
  return (m === 1 && day >= 17 && day <= 31) || (m === 7 && day >= 1 && day <= 15)
}

/** 红灯数 → 仓位上限（v4.1） */
function redCountToCap(redCount, hardCount, softCount) {
  let cap = 0.8
  if (redCount >= 4) cap = 0
  else if (redCount >= 3) cap = 0.1
  else if (redCount >= 2) cap = 0.3
  else if (redCount >= 1) cap = 0.5
  // 硬灯 ≥ 2 → 直接 ≤10%
  if (hardCount >= 2) cap = Math.min(cap, 0.1)
  // 软灯单独：上限 ≤30%，不到 0
  if (hardCount <= 0 && softCount > 0) {
    cap = 0.3
  }
  return cap
}

function levelForCap(cap) {
  if (cap <= 0 || cap <= 0.1) return 'danger'
  if (cap <= 0.5) return 'warning'
  return 'safe'
}

export function maxHighSinceBuy(k, pos) {
  if (!k) return 0
  if (pos?.date && k.klines?.length) {
    const buyDate = String(pos.date).slice(0, 10)
    let max = 0
    k.klines.forEach((bar) => {
      if (bar?.date >= buyDate && bar.high > max) max = bar.high
    })
    if (max > 0) return max
  }
  return 0
}

function ma20At(bars, idx) {
  if (!bars || idx < 19) return 0
  let sum = 0
  for (let j = idx - 19; j <= idx; j++) sum += bars[j].close || 0
  return sum / 20
}

function ma60At(bars, idx) {
  if (!bars || idx < 59) return 0
  let sum = 0
  for (let j = idx - 59; j <= idx; j++) sum += bars[j].close || 0
  return sum / 60
}

/** 连续收盘 < MA20×buf 的天数。
 * 缓冲带内（MA20×buf ≤ close < MA20）不计入、也不清零 streak；
 * 仅收盘 ≥ MA20 才算站回、重置计数。
 */
function consecutiveMa20BreakDays(bars, buf = MA20_BREAK_BUF) {
  if (!bars?.length) return 0
  let n = 0
  for (let i = bars.length - 1; i >= 19; i--) {
    const ma = ma20At(bars, i)
    const close = Number(bars[i]?.close) || 0
    if (!(ma > 0 && close > 0)) break
    if (close < ma * buf) n += 1
    else if (close < ma) continue // 缓冲带：观察，streak 保持
    else break // 站回 MA20
  }
  return n
}

/** 指数连续 N 日收盘跌破 MA60 */
function consecutiveBelowMa60(k, need = INDEX_BREAK_CONFIRM_DAYS) {
  const bars = k?.klines
  if (!bars?.length || bars.length < 60) return { ok: false, days: 0 }
  let n = 0
  for (let i = bars.length - 1; i >= 59; i--) {
    const ma = ma60At(bars, i)
    const close = Number(bars[i]?.close) || 0
    if (!(ma > 0 && close > 0)) break
    if (close < ma) n += 1
    else break
  }
  return { ok: n >= need, days: n }
}

export function isStrongTrend(k) {
  if (!(Number(k?.change20d) > 10)) return false
  const bars = k?.klines
  if (!bars?.length || bars.length < 25) return false
  const i = bars.length - 1
  const maNow = ma20At(bars, i)
  const maPrev = ma20At(bars, i - 5)
  return maNow > 0 && maPrev > 0 && maNow > maPrev
}

function tradingDaysHeld(k, pos) {
  if (!pos?.date) return 0
  const buyDate = String(pos.date).slice(0, 10)
  if (!k?.klines?.length) return 0 // 无 K 线不猜日历日，避免假时间止损
  const n = k.klines.filter((b) => b?.date >= buyDate).length
  // 买入日早于缓存窗口 → 样本不全，不触发时间止损
  const oldest = k.klines[0]?.date
  if (oldest && buyDate < oldest) return 0
  return n
}

function limitDownPct(code, name) {
  code = String(code || '').replace(/^(sh|sz)/, '')
  if (/^(300|301|688)/.test(code)) return -19.9
  if (String(name || '').includes('ST')) return -4.9
  return -9.9
}

/** 腾讯指数成交额多为「万元」→ 亿元。 */
export function indexAmountYi(quote) {
  const a = Number(quote?.amount)
  if (!(a > 0) || !Number.isFinite(a)) return null
  return a / 10000
}

export function fmtYi(n, { signed = false } = {}) {
  if (n == null || !Number.isFinite(n)) return '--'
  const abs = Math.abs(n)
  let body
  if (abs >= 1000) body = `${(abs / 10000).toFixed(2)}万亿`
  else if (abs >= 100) body = `${Math.round(abs)}亿`
  else if (abs >= 10) body = `${abs.toFixed(0)}亿`
  else body = `${abs.toFixed(1)}亿`
  if (!signed) return body
  return `${n >= 0 ? '+' : '-'}${body}`
}

/**
 * 单指数量能：量比定放缩；成交额为该市场当日累计。
 * 注意：量比不是「较上日此时」；三市较上日此时见 marketTurnover。
 */
export function describeIndexVolume(quote) {
  const lb = Number(quote?.liangbi)
  const amountYi = indexAmountYi(quote)
  const hasLb = Number.isFinite(lb) && lb > 0
  let state = 'unknown'
  let tag = '量--'
  if (hasLb) {
    if (lb >= 1.2) {
      state = 'expand'
      tag = '放量'
    } else if (lb >= 1.05) {
      state = 'mild'
      tag = '温放'
    } else if (lb >= 0.9) {
      state = 'flat'
      tag = '平量'
    } else {
      state = 'shrink'
      tag = '缩量'
    }
  }
  const liangbi = hasLb ? Math.round(lb * 100) / 100 : null
  return {
    state,
    tag,
    liangbi,
    amountYi: amountYi != null ? Math.round(amountYi * 10) / 10 : null,
    deltaYi: null,
    deltaText: '--',
    amountText: amountYi != null ? fmtYi(amountYi) : '--',
    liangbiText: liangbi != null ? String(liangbi) : '--',
    tip: [
      liangbi != null ? `量比 ${liangbi}（近几日同时段）` : null,
      amountYi != null ? `成交额 ${fmtYi(amountYi)}` : null,
      '量比≠较上日此时；三市对比看左侧「三市」卡片',
    ].filter(Boolean).join(' · '),
  }
}

/** 量能对比：量比 / 较昨 / 较前5日均 / 自选放量占比。 */
export function computeVolumeBrief({ items, quotes, klines, indices }) {
  const sh = indices?.sh000001 || quotes?.sh000001 || {}
  const cy = indices?.sz399006 || quotes?.sz399006 || {}
  const shK = klines?.sh000001 || {}
  const bars = shK.klines || []
  const shVol = describeIndexVolume(sh)

  const liangbi = Number(sh.liangbi)
  const cyLiangbi = Number(cy.liangbi)
  const todayVol = Number(sh.volume) || (bars.length ? Number(bars[bars.length - 1]?.volume) : 0) || 0
  const yestVol = bars.length >= 2 ? Number(bars[bars.length - 2]?.volume) || 0 : 0
  const prior = bars.length > 5 ? bars.slice(-6, -1) : bars.slice(0, -1)
  const avgVol5 = prior.length
    ? prior.reduce((s, b) => s + (Number(b.volume) || 0), 0) / prior.length
    : (Number(shK.avgVol5) || 0)

  const vsYest = todayVol > 0 && yestVol > 0 ? todayVol / yestVol : null
  const vsAvg5 = todayVol > 0 && avgVol5 > 0 ? todayVol / avgVol5 : null

  const stockItems = (items || []).filter((i) => i.type !== 'etf')
  let volExpanded = 0
  let volTotal = 0
  stockItems.forEach((i) => {
    const k = klines?.[i.code]
    const q = quotes?.[i.code]
    if (k?.klines?.length >= 2 && q?.volume > 0) {
      volTotal++
      if (q.volume > k.klines[k.klines.length - 2].volume) volExpanded++
    }
  })
  const watchExpandPct = volTotal ? Math.round((volExpanded / volTotal) * 1000) / 10 : null

  // 优先用上证量比（盘中可比）；缺省再看较昨 / 自选占比
  const primary = Number.isFinite(liangbi) && liangbi > 0
    ? liangbi
    : (vsYest != null ? vsYest : null)
  let state = shVol.state
  let label = shVol.tag === '量--' ? '量能--' : shVol.tag === '温放' ? '温和放量' : shVol.tag

  const fmtRatioPct = (r) => {
    if (r == null || !Number.isFinite(r)) return '--'
    const pct = (r - 1) * 100
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(0)}%`
  }

  const tipParts = []
  if (shVol.liangbi != null) tipParts.push(`上证量比 ${shVol.liangbi}`)
  if (shVol.amountYi != null) tipParts.push(`上证成交额 ${fmtYi(shVol.amountYi)}`)
  if (vsYest != null) tipParts.push(`上证较昨量 ${fmtRatioPct(vsYest)}（全日比，盘中偏低）`)
  if (watchExpandPct != null) tipParts.push(`自选放量 ${volExpanded}/${volTotal}（${watchExpandPct}%）`)
  if (Number.isFinite(cyLiangbi) && cyLiangbi > 0) tipParts.push(`创业量比 ${cyLiangbi.toFixed(2)}`)

  return {
    state,
    label,
    tone: state === 'expand' || state === 'mild' ? 'up' : state === 'shrink' ? 'down' : '',
    liangbi: shVol.liangbi,
    cyLiangbi: Number.isFinite(cyLiangbi) && cyLiangbi > 0 ? Math.round(cyLiangbi * 100) / 100 : null,
    amountYi: shVol.amountYi,
    deltaYi: null,
    deltaText: '--',
    amountText: shVol.amountText,
    vsYest,
    vsYestPct: fmtRatioPct(vsYest),
    vsAvg5,
    vsAvg5Pct: fmtRatioPct(vsAvg5),
    watchExpandPct,
    watchExpanded: volExpanded,
    watchTotal: volTotal,
    primary,
    met: primary != null ? primary >= 1.1 : (watchExpandPct != null ? watchExpandPct > 50 : null),
    tip: tipParts.join(' · ') || '量能数据不足',
    short: [
      shVol.liangbi != null ? `量比${shVol.liangbi}` : null,
      shVol.amountYi != null ? shVol.amountText : null,
      watchExpandPct != null ? `自选${watchExpandPct}%` : null,
    ].filter(Boolean).join(' · ') || '--',
  }
}

export function computeConditions({ items, quotes, klines, marketBreadth, breadth, indices }) {
  const stockItems = items.filter((i) => i.type !== 'etf')
  const withPrice = stockItems.filter((i) => quotes[i.code]?.price > 0)
  const notFallen = withPrice.filter((i) => {
    const q = quotes[i.code]
    return q.price >= q.open
  }).length
  const cond1 = withPrice.length ? notFallen / withPrice.length > 0.6 : null
  const breadthSrc = marketBreadth?.total > 0 ? marketBreadth : breadth
  const cond2 = breadthSrc?.total > 0 ? breadthSrc.up / breadthSrc.total > 0.6 : null
  const tech = withPrice.filter((i) => {
    const s = getSector(i.code)
    return /半导体|CPO|PCB|AI|算力/.test(s)
  })
  const techPos = tech.filter((i) => quotes[i.code].changePct > 0).length
  const cond3 = tech.length ? techPos / tech.length > 0.7 : null
  const vol = computeVolumeBrief({ items, quotes, klines, indices })
  const cond4 = vol.met
  const volName = vol.state === 'unknown' ? '放量' : vol.label
  return [
    { name: '高开不回落', met: cond1 },
    { name: '上涨>6成', met: cond2 },
    { name: '科技翻红', met: cond3 },
    { name: volName, met: cond4, detail: vol.tip },
  ]
}

export function computeLamps({ quotes, klines, overseas, limitUpStats, indices }) {
  const lamps = []
  const lu = limitUpStats || {}

  // 1 指数破位：沪深300 / 创业板 连续3日收盘破 MA60（K线不足则不点亮，避免单日误判）
  const nameMap = { sh000300: '沪深300', sz399006: '创业板' }
  const broken = []
  let known = 0
  INDEX_BREAK_CODES.forEach((code) => {
    const k = klines?.[code] || {}
    if (k?.klines?.length >= 60) {
      known += 1
      const r = consecutiveBelowMa60(k, INDEX_BREAK_CONFIRM_DAYS)
      if (r.ok) broken.push(`${nameMap[code] || code}${r.days}日`)
    }
  })
  const breakRed = broken.length > 0
  lamps.push({
    id: 'index_break',
    name: '指数破位',
    red: breakRed,
    kind: 'hard',
    weight: 1,
    detail: known
      ? (broken.length ? `${broken.join('、')}破MA60` : `沪深300/创业未连破MA60（样本${known}）`)
      : '指数均线样本不足（等K线刷新）',
  })

  // 2 海外冲击
  const nasEtf = quotes?.sz159659
  const nasIdx = overseas?.nasdaq
  const nasChg = nasEtf?.changePct != null
    ? nasEtf.changePct
    : (nasIdx?.changePct != null ? nasIdx.changePct : null)
  const overseasRed = !!(overseas && overseas.changePct != null && overseas.changePct <= OVERSEAS_SPX_RED)
    || (nasChg != null && nasChg <= OVERSEAS_QQQ_RED)
  let od = (overseas && overseas.changePct != null) ? `标普 ${overseas.changePct.toFixed(2)}%` : ''
  if (nasEtf?.changePct != null) od += `${od ? ' | ' : ''}纳指ETF ${nasEtf.changePct.toFixed(2)}%`
  else if (nasIdx?.changePct != null) od += `${od ? ' | ' : ''}纳指 ${nasIdx.changePct.toFixed(2)}%`
  lamps.push({
    id: 'overseas',
    name: '海外冲击',
    red: overseasRed,
    kind: 'hard',
    weight: 1,
    detail: od ? `${od}（≤${OVERSEAS_SPX_RED}% / ≤${OVERSEAS_QQQ_RED}%）` : '海外数据不足',
  })

  // 3 生态恶化：昨涨停今亏≥3 / 跌停≥10 /（样本充足时）连板高度≤2
  const zt = Number(lu.zt) || 0
  const dt = Number(lu.dt) || 0
  const maxDays = Number(lu.maxDays) || 0
  const yestLoss = Number(lu.yestLoss != null ? lu.yestLoss : lu.bigDrawdown) || 0
  const ecoReasons = []
  if (yestLoss >= ECO_YEST_LOSS_RED) ecoReasons.push(`昨涨停今亏${yestLoss}家`)
  if (dt >= ECO_DT_RED) ecoReasons.push(`跌停${dt}家`)
  // maxDays=0 常为池样本空，不当作「高度≤2」；需有可读高度且涨停样本够
  if (zt >= 20 && maxDays >= 1 && maxDays <= ECO_MAX_DAYS_COLD) {
    ecoReasons.push(`连板高度${maxDays}≤${ECO_MAX_DAYS_COLD}`)
  }
  lamps.push({
    id: 'eco_stress',
    name: '生态恶化',
    red: ecoReasons.length > 0,
    kind: 'hard',
    weight: 1,
    detail: ecoReasons.length
      ? ecoReasons.join('；')
      : `昨亏${yestLoss} / 跌停${dt} / 高标${maxDays}板`,
  })

  // 4 业绩窗口（软）
  const earn = isEarningsWindow()
  lamps.push({
    id: 'earnings',
    name: '业绩窗口',
    red: earn,
    kind: 'soft',
    weight: 1,
    detail: earn ? '披露高峰窗口（软灯）' : '非业绩窗口',
  })

  // 5 杠杆退潮（软·手动）
  const lever = getLeverOverride()
  lamps.push({
    id: 'leverage',
    name: '杠杆退潮',
    red: lever,
    kind: 'soft',
    weight: 1,
    manual: true,
    detail: lever ? '已手动标记：两融连续约5日下降' : '未标记；点击可手动切换（软灯）',
  })
  return lamps
}

export function positionRecFromLamps(lamps) {
  let hardCount = 0
  let softCount = 0
  let lit = 0
  ;(lamps || []).forEach((l) => {
    if (!l.red) return
    lit += 1
    if (l.kind === 'soft') softCount += 1
    else hardCount += 1
  })
  const lampCap = redCountToCap(lit, hardCount, softCount)
  const level = levelForCap(lampCap)
  const riskScore = lit
  let text
  if (lampCap <= 0) text = `${lit}盏亮 | 仓位归零！只卖不买`
  else text = `${lit}盏亮 | 仓位上限${Math.round(lampCap * 10)}成`
  return {
    redCount: lit,
    hardCount,
    softCount,
    hardScore: hardCount,
    softScore: softCount,
    riskScore,
    text,
    level,
    lampCap,
  }
}

/** 上涨占比 <40% 或上涨家数 <1500 → 情绪退潮，仓位硬顶 3 成且只卖不买 */
export function sentimentRetreat(marketBreadth, breadth) {
  const mb = marketBreadth?.total > 0 ? marketBreadth : breadth
  if (!mb?.total) return null
  const upPct = mb.up / mb.total
  if (!(upPct < 0.4 || (marketBreadth?.total > 0 && mb.up < 1500))) return null
  return {
    active: true,
    upPct,
    up: mb.up,
    total: mb.total,
    cap: 0.3,
    buyAllowed: false,
  }
}

/** 全市场情绪六段（养家骨架 · 展示启发式） */
export const EMOTION_CYCLE_STEPS = [
  { id: 'ice', label: '冰点' },
  { id: 'thaw', label: '回暖' },
  { id: 'ferment', label: '发酵' },
  { id: 'climax', label: '高潮' },
  { id: 'diverge', label: '分歧' },
  { id: 'retreat', label: '退潮' },
]

export function computeEmotionCycle(ctx) {
  const retreat = sentimentRetreat(ctx.marketBreadth, ctx.breadth)
  const ice = getMainRiseIce()
  const mb = ctx.marketBreadth?.total > 0 ? ctx.marketBreadth : ctx.breadth
  const up = Number(mb?.up) || 0
  const total = Number(mb?.total) || 0
  const upPct = total > 0 ? up / total : null
  const lu = ctx.limitUpStats || {}
  const zt = Number(lu.zt) || 0
  const zb = Number(lu.zb) || 0
  const dt = Number(lu.dt) || 0
  const maxDays = Number(lu.maxDays) || 0
  const breakRate = lu.breakRate != null && Number.isFinite(Number(lu.breakRate))
    ? Number(lu.breakRate)
    : (zt + zb > 0 ? Math.round((zb / (zt + zb)) * 1000) / 10 : null)
  const yestPremium = lu.yestPremium != null && Number.isFinite(Number(lu.yestPremium))
    ? Number(lu.yestPremium)
    : null

  let id = 'thaw'
  let label = '回暖'
  let conf = 'low'
  let reason = '默认修复阶段（启发式）'

  if (retreat) {
    id = 'retreat'
    label = '退潮'
    conf = 'high'
    reason = `情绪退潮：上涨${up}家` + (upPct != null ? `（${(upPct * 100).toFixed(0)}%）` : '')
  } else if (
    (zt >= 80 && maxDays >= 4 && (yestPremium == null || yestPremium >= 0))
    || (zt >= 100 && maxDays >= 5)
  ) {
    id = 'climax'
    label = '高潮'
    conf = 'medium'
    reason = `涨停${zt} · 最高${maxDays}连 · 偏拥挤`
  } else if (
    breakRate != null && breakRate >= 35
    && (yestPremium != null && yestPremium < 0)
    && zt >= 20
  ) {
    id = 'diverge'
    label = '分歧'
    conf = 'medium'
    reason = `破板${breakRate.toFixed(0)}% · 昨涨停溢价${yestPremium.toFixed(1)}%`
  } else if (
    ice
    || (total > 0 && up < 1500 && zt < 30 && (yestPremium == null || yestPremium <= 0))
  ) {
    id = 'ice'
    label = '冰点'
    conf = ice ? 'high' : 'low'
    reason = ice
      ? '已手动确认昨日冰点'
      : `广度偏冷：上涨${up} · 涨停${zt}（自动仅供参考）`
  } else if (
    (zt >= 50 && maxDays >= 2 && (breakRate == null || breakRate < 30))
    || (upPct != null && upPct >= 0.55 && zt >= 40)
  ) {
    id = 'ferment'
    label = '发酵'
    conf = 'medium'
    reason = `赚钱效应扩散：涨停${zt} · 连板高${maxDays}`
  } else {
    id = 'thaw'
    label = '回暖'
    conf = 'low'
    reason = upPct != null
      ? `上涨占比${(upPct * 100).toFixed(0)}% · 涨停${zt} · 跌停${dt}`
      : `涨停${zt} · 跌停${dt}`
  }

  const idx = EMOTION_CYCLE_STEPS.findIndex((s) => s.id === id)
  return {
    id,
    label,
    conf,
    reason,
    index: idx >= 0 ? idx : 1,
    steps: EMOTION_CYCLE_STEPS,
    tip: `情绪阶段假说「${label}」·${conf === 'high' ? '高' : conf === 'medium' ? '中' : '低'}置信 · ${reason} · 见情绪周期与量价假说.md`,
  }
}

/**
 * 个股量价假说（野人四阶段骨架）。
 * 返回 null 表示数据不足不展示。
 */
export function computeVolumePhase(q, k) {
  const price = Number(q?.price) || 0
  const vol = Number(q?.volume) || 0
  const chg = Number(q?.changePct)
  const lb = Number(q?.liangbi) || 0
  const ma20 = Number(k?.ma20) || 0
  const c20 = Number(k?.change20d)
  const c60 = Number(k?.change60d)
  const avg5 = Number(k?.avgVol5) || 0
  if (!(price > 0) || !Number.isFinite(chg)) return null

  const volRatio = avg5 > 0 && vol > 0 ? vol / avg5 : (lb > 0 ? lb : null)
  const highPos = Number.isFinite(c60) && c60 > HIGH_60D_PCT
  const midHigh = Number.isFinite(c20) && c20 > 25
  const aboveMa = ma20 > 0 && price >= ma20

  // 出货：铁律5同向，或高位放量滞涨/大跌
  if (highPos && avg5 > 0 && vol >= avg5 * 2 && chg <= BIG_DROP_PCT) {
    return {
      id: 'distribute',
      label: '偏出货',
      conf: 'high',
      tip: `高位巨量长阴假说：60日+${c60.toFixed(0)}% · 量${volRatio?.toFixed(1)}倍 · 见量价与主力行为.md`,
    }
  }
  if (highPos && volRatio != null && volRatio >= 1.8 && chg > -2 && chg < 2) {
    return {
      id: 'distribute',
      label: '偏出货',
      conf: 'medium',
      tip: `高位放量滞涨假说：60日+${c60.toFixed(0)}% · 量比/量能偏大`,
    }
  }
  if ((highPos || midHigh) && volRatio != null && volRatio >= 2 && chg <= -3) {
    return {
      id: 'distribute',
      label: '偏出货',
      conf: 'medium',
      tip: `放量下跌假说：涨幅已大且今日${chg.toFixed(1)}%`,
    }
  }

  // 拉升
  if (aboveMa && Number.isFinite(c20) && c20 > 5 && (lb >= 1.2 || (volRatio != null && volRatio >= 1.2)) && chg > 0) {
    return {
      id: 'markup',
      label: '偏拉升',
      conf: 'medium',
      tip: `站上MA20 · 20日+${c20.toFixed(1)}% · 放量上行（中置信假说）`,
    }
  }

  // 洗盘：回调缩量（低置信）
  if (aboveMa && chg < -0.5 && volRatio != null && volRatio < 0.85 && Number.isFinite(c20) && c20 > 0) {
    return {
      id: 'wash',
      label: '偏洗盘',
      conf: 'low',
      tip: `缩量回调假说：量${volRatio.toFixed(2)}倍均量 · 低置信，假洗=出货`,
    }
  }
  if (aboveMa && chg < -1 && lb > 0 && lb < 0.9 && Number.isFinite(c20) && c20 > 0) {
    return {
      id: 'wash',
      label: '偏洗盘',
      conf: 'low',
      tip: `量比${lb.toFixed(2)}偏弱回调 · 低置信假说`,
    }
  }

  // 吸筹/建仓：低位温和放量（最低置信）
  const lowPos = (!Number.isFinite(c60) || c60 < 25) && (!Number.isFinite(c20) || c20 < 15)
  if (lowPos && chg >= 0 && ((volRatio != null && volRatio >= 1.3 && volRatio < 2.5) || (lb >= 1.3 && lb < 2.5))) {
    return {
      id: 'accumulate',
      label: '偏吸筹',
      conf: 'low',
      tip: '低位温和放量假说 · 低置信，禁止当买入指令',
    }
  }

  return {
    id: 'unknown',
    label: '量价不明',
    conf: 'low',
    tip: '样本不足或形态混杂，不做阶段认定',
  }
}

/**
 * 有效仓位 = min(五灯上限, 情绪退潮上限)。
 * 两套规则并行时取更严，避免「0红→8成」与「情绪退潮→3成」并排打架。
 */
export function effectivePositionRec(ctx) {
  const lamps = ctx.lamps || computeLamps(ctx)
  const base = positionRecFromLamps(lamps)
  const retreat = sentimentRetreat(ctx.marketBreadth, ctx.breadth)
  const lampCap = base.lampCap ?? 0.8
  if (!retreat) {
    return {
      ...base,
      lampCap,
      sentimentCap: null,
      cap: lampCap,
      buyAllowed: lampCap > 0,
      detail: '',
    }
  }
  const cap = Math.min(lampCap, retreat.cap)
  const tighter = retreat.cap < lampCap
  let text
  let level = base.level
  if (cap <= 0) {
    text = '仓位归零！只卖不买'
    level = 'danger'
  } else if (tighter) {
    text = `有效≤${Math.round(cap * 10)}成（情绪退潮）`
    level = level === 'safe' ? 'warning' : level
  } else {
    text = base.text
  }
  return {
    ...base,
    lampCap,
    sentimentCap: retreat.cap,
    cap,
    buyAllowed: false,
    level,
    text,
    detail: tighter
      ? `五灯${base.redCount}红本可${Math.round(lampCap * 10)}成，情绪退潮（上涨${(retreat.upPct * 100).toFixed(0)}%/${retreat.up}家）压至${Math.round(cap * 10)}成，只卖不买`
      : `情绪退潮中；五灯已更严（≤${Math.round(lampCap * 10)}成）`,
  }
}

export function computeAlerts(ctx) {
  const {
    items, quotes, klines, positions, marketBreadth, breadth, overseas,
  } = ctx
  const alerts = []
  const heldCodes = Object.keys(positions || {})
  if (!heldCodes.length) return alerts

  const lamps = computeLamps(ctx)
  const lampRec = positionRecFromLamps(lamps)
  if (lampRec.lampCap <= 0) {
    alerts.push({ level: 'danger', code: 'ALL', name: '全部持仓', msg: `五灯${lampRec.redCount}红触顶归零`, action: '立即清仓' })
  } else if (lampRec.lampCap <= 0.1) {
    alerts.push({ level: 'danger', code: 'ALL', name: '全部持仓', msg: `五灯${lampRec.redCount}红，仓位上限1成`, action: '减仓至1成' })
  }

  const retreat = sentimentRetreat(marketBreadth, breadth)
  if (retreat) {
    const lampCap = lampRec.lampCap ?? 0.8
    const effective = Math.min(lampCap, retreat.cap)
    alerts.push({
      level: 'warning', code: 'ALL', name: '情绪退潮',
      msg: `上涨${(retreat.upPct * 100).toFixed(0)}%（${retreat.up}家）`,
      action: lampCap > retreat.cap
        ? `只卖不买，有效仓位≤${Math.round(effective * 10)}成（压过五灯${Math.round(lampCap * 10)}成）`
        : `只卖不买，仓位≤${Math.round(effective * 10)}成`,
    })
  }

  heldCodes.forEach((fullCode) => {
    const pos = positions[fullCode]
    const item = items.find((i) => i.code === fullCode)
    const q = quotes[fullCode]
    const k = klines[fullCode]
    const name = item?.name || pos?.name || fullCode
    if (!q || q.price <= 0) {
      alerts.push({ level: 'warning', code: fullCode, name, msg: '行情数据缺失', action: '人工核对' })
      return
    }
    const price = q.price
    const buyPrice = pos.buyPrice
    const pnlPct = buyPrice > 0 ? (price - buyPrice) / buyPrice * 100 : 0
    let maxHigh = maxHighSinceBuy(k, pos)
    if (maxHigh <= 0) maxHigh = price
    const maxProfitPct = buyPrice > 0 ? (maxHigh - buyPrice) / buyPrice * 100 : 0
    const drawdownFromHigh = maxHigh > 0 ? (price - maxHigh) / maxHigh * 100 : 0
    const strong = isStrongTrend(k)
    const belowMA20 = k?.ma20 > 0 && price < k.ma20
    const breakDays = consecutiveMa20BreakDays(k?.klines, MA20_BREAK_BUF)

    // 铁律1：缓冲带 + 3日减半 / 5日清仓；同时破20+60立即清仓
    if (k?.ma20 > 0 && belowMA20 && k.ma60 > 0 && price < k.ma60) {
      alerts.push({ level: 'danger', code: fullCode, name, msg: `跌破20/60日线`, action: '铁律1：清仓' })
    } else if (breakDays >= IRON1_CLEAR_DAYS) {
      alerts.push({
        level: 'danger', code: fullCode, name,
        msg: `连续${breakDays}日收盘<MA20×${MA20_BREAK_BUF}`,
        action: '铁律1：清仓',
      })
    } else if (breakDays >= IRON1_HALF_DAYS) {
      alerts.push({
        level: 'danger', code: fullCode, name,
        msg: `连续${breakDays}日收盘<MA20×${MA20_BREAK_BUF}`,
        action: '铁律1：减半仓',
      })
    } else if (breakDays >= 1) {
      alerts.push({
        level: 'warning', code: fullCode, name,
        msg: `已${breakDays}日收盘<MA20×${MA20_BREAK_BUF}（需${IRON1_HALF_DAYS}日减半）`,
        action: '铁律1：观察确认中',
      })
    } else if (belowMA20 && breakDays === 0) {
      alerts.push({
        level: 'warning', code: fullCode, name,
        msg: `收盘在MA20缓冲带内(${k.ma20.toFixed(2)})`,
        action: '铁律1：观察',
      })
    }

    const ddThr = strong ? DRAWDOWN_ALERT_STRONG : DRAWDOWN_ALERT_PCT
    if (maxProfitPct >= PROFIT_TAKE_PCT && drawdownFromHigh <= -ddThr) {
      alerts.push({
        level: 'danger', code: fullCode, name,
        msg: `浮盈曾达${maxProfitPct.toFixed(1)}%，回撤${drawdownFromHigh.toFixed(1)}%${strong ? '(强趋势)' : ''}`,
        action: '铁律2：清掉剩余仓位',
      })
    }
    if (maxProfitPct >= PROFIT_GREEN_PCT && pnlPct <= 0.5 && pnlPct >= -0.5 && drawdownFromHigh <= -PROFIT_GREEN_CONFIRM_PCT) {
      alerts.push({ level: 'danger', code: fullCode, name, msg: `浮盈翻绿附近(${pnlPct.toFixed(2)}%)`, action: '铁律3：保本出局' })
    }
    if (maxProfitPct >= PROFIT_GREEN_PCT && pnlPct < 0 && (drawdownFromHigh <= -PROFIT_GREEN_CONFIRM_PCT || belowMA20)) {
      alerts.push({ level: 'danger', code: fullCode, name, msg: `曾盈利现已亏损(${pnlPct.toFixed(2)}%)`, action: '立即卖出' })
    }
    if (k?.change60d > HIGH_60D_PCT && k.avgVol5 > 0 && q.volume > 0 && q.changePct <= BIG_DROP_PCT) {
      const volRatio = q.volume / k.avgVol5
      if (volRatio >= 2) {
        alerts.push({ level: 'danger', code: fullCode, name, msg: `高位巨量长阴 量比${volRatio.toFixed(1)}`, action: '铁律5：清仓' })
      }
    }

    const heldDays = tradingDaysHeld(k, pos)
    if (heldDays >= TIME_STOP_DAYS && pnlPct < 0) {
      alerts.push({
        level: 'danger', code: fullCode, name,
        msg: `持仓${heldDays}日仍浮亏${pnlPct.toFixed(2)}%`,
        action: '时间止损：市价卖出',
      })
    }

    const levels = positionRiskLevels(pos, price, {
      code: fullCode, name, maxHigh, strongTrend: strong,
    })
    if (levels?.takeProfitSource === 'custom' && levels.takeHit) {
      alerts.push({
        level: 'warning', code: fullCode, name,
        msg: `现价触及自定义止盈(${levels.takeProfit.toFixed(2)})`,
        action: '强制兑现部分',
      })
    } else if (levels?.takeProfitSource === 'auto') {
      if (pnlPct >= PROFIT_TAKE_L3) {
        alerts.push({ level: 'warning', code: fullCode, name, msg: `盈利${pnlPct.toFixed(1)}%达三级止盈`, action: '止盈：清仓或留1/4' })
      } else if (pnlPct >= PROFIT_TAKE_L2) {
        alerts.push({ level: 'warning', code: fullCode, name, msg: `盈利${pnlPct.toFixed(1)}%达二级止盈`, action: '止盈：再卖1/3' })
      } else if (pnlPct >= PROFIT_TAKE_PCT) {
        alerts.push({ level: 'warning', code: fullCode, name, msg: `盈利${pnlPct.toFixed(1)}%达一级止盈`, action: '止盈：卖出1/3~1/2' })
      }
    }
    if (levels?.stopHit) {
      const kind = levels.costHit ? '成本止损' : '跟踪止损'
      const src = levels.stopLossSource === 'custom' ? '自定义止损' : `${levels.boardLabel}${kind}`
      alerts.push({
        level: 'danger',
        code: fullCode,
        name,
        msg: `现价触及${src}(${(levels.costHit ? levels.stopLoss : levels.trailStop).toFixed(2)})`,
        action: '立即止损卖出',
      })
    }

    if (q.weibi && q.weibi < -30) {
      alerts.push({ level: 'warning', code: fullCode, name, msg: `委比${q.weibi.toFixed(1)}%恶化`, action: '注意卖压' })
    }
    const ld = limitDownPct(item?.rawCode || fullCode, name)
    if (q.changePct <= ld) {
      alerts.push({ level: 'danger', code: fullCode, name, msg: `跌停(${q.changePct.toFixed(2)}%)`, action: '挂单排队' })
    } else if (q.changePct <= -5) {
      alerts.push({ level: 'warning', code: fullCode, name, msg: `今日跌${q.changePct.toFixed(2)}%`, action: '关注止损/20日线' })
    }
  })

  // dedupe sell alerts per code keep highest priority (P0>P1>P2)
  const sellScore = (a) => {
    if (a.action.includes('时间止损') || a.action.includes('止损')) return 10
    if (a.action.includes('清仓')) return 9
    if (a.action.includes('立即卖出')) return 8
    if (a.action.includes('清掉剩余')) return 7
    if (a.action.includes('减半')) return 6
    if (a.action.includes('保本')) return 5
    if (a.action.includes('止盈')) return 4
    return 0
  }
  const best = {}
  const out = []
  alerts.forEach((a) => {
    const sc = sellScore(a)
    if (sc > 0) {
      if (!best[a.code] || sc > best[a.code].score) best[a.code] = { score: sc, alert: a }
    } else out.push(a)
  })
  Object.values(best).forEach((x) => out.push(x.alert))
  return out
}

export function effectiveRating(item, ctx) {
  const { quotes, klines, positions, analyses, staleDays, lamps, ...rest } = ctx || {}
  const fc = item.code
  const a = analyses?.[fc]
  if (positions?.[fc]) return '持仓'
  if ((a && a.ratingManual === '排除') || (item.rating === '排除' && !item.autoRating)) return '排除'
  const q = quotes?.[fc]
  const k = klines?.[fc]
  const ls = liveScoreFrom(q, k, {
    code: fc,
    sector: item.sector,
    industry: q?.industry || item.industry || '',
  })
  if (ls == null) return item.rating || '观察'
  let raw = ratingFromScore(ls)
  if (raw !== '可买入') return raw
  if (!isRiskCleared(a, staleDays)) return '观察'
  // 偏离门禁：现价 > MA20×1.05 → 不追
  if (k?.ma20 > 0 && q?.price > 0 && q.price > k.ma20 * (1 + BUY_MAX_MA20_DEV)) return '不追'
  // 买前问：已知量比 ≤ 1.0 → 观察；缺失/0 不因缺数误杀
  const lb = Number(q?.liangbi)
  if (Number.isFinite(lb) && lb > 0 && lb <= 1.0) return '观察'
  // 五灯 ≤ 2 红
  const lampList = lamps || computeLamps({ quotes, klines, ...rest })
  const rec = positionRecFromLamps(lampList)
  if (rec.redCount > 2) return '观察'
  // 与盘面纪律一致：情绪退潮 / 仓位归零时不得「可买入」
  const retreat = sentimentRetreat(ctx?.marketBreadth, ctx?.breadth)
  if (retreat || rec.lampCap <= 0) return '观察'
  return '可买入'
}

export function computeMainRise({ items, quotes, indices, klines, marketBreadth, breadth, limitUpStats }) {
  const ice = getMainRiseIce()
  const mb = marketBreadth?.total > 0 ? marketBreadth : breadth
  const upPct = mb?.total > 0 ? mb.up / mb.total : null

  const stockItems = (items || []).filter((i) => i.type !== 'etf')
  const withPrice = stockItems.filter((i) => quotes[i.code]?.price > 0)
  const tech = withPrice.filter((i) => /半导体|CPO|PCB|AI|算力/.test(getSector(i.code)))
  const techUp = tech.filter((i) => quotes[i.code].changePct > 0).length
  const techPct = tech.length ? techUp / tech.length : 0

  const vol = computeVolumeBrief({ items, quotes, klines, indices })
  const zt = limitUpStats?.zt || 0
  const zb = limitUpStats?.zb || 0
  const dt = limitUpStats?.dt || 0
  const maxDays = limitUpStats?.maxDays || 0
  const zbRate = zt + zb > 0 ? zb / (zt + zb) : null
  const zbStr = zbRate != null ? `${(zbRate * 100).toFixed(0)}%` : '--'

  const checks = [
    {
      name: '昨日冰点已确认',
      met: ice,
      manual: true,
      unknown: false,
      detail: ice ? '已手动确认：昨日上涨<1500家或涨停负溢价' : '点击确认昨日为冰点（上涨<1500家/涨停无溢价）',
    },
    {
      name: '全市场赚钱效应扩散',
      met: upPct != null && upPct > 0.6,
      unknown: upPct == null,
      detail: upPct != null ? `全市场上涨 ${(upPct * 100).toFixed(0)}%（${mb.up}家，需>60%）` : '全市场数据缺失',
    },
    {
      name: '量能放大',
      met: vol.met === true,
      unknown: vol.met == null,
      detail: vol.tip || '量能数据缺失',
    },
    {
      name: '科技主线明确',
      met: tech.length > 0 && techPct > 0.7,
      unknown: tech.length === 0,
      detail: tech.length > 0 ? `科技板块翻红 ${techUp}/${tech.length}（${(techPct * 100).toFixed(0)}%>70%）` : '科技样本数据不足',
    },
    {
      name: '涨停梯队健康',
      met: zt >= 50 && zbRate != null && zbRate < 0.3 && maxDays >= 2,
      unknown: zt === 0,
      detail: zt > 0 ? `涨停 ${zt} 家，炸板率 ${zbStr}，最高连板 ${maxDays} 板` : '涨停池数据缺失',
    },
    {
      name: '亏钱效应收敛',
      met: zt > 0 && dt <= 20 && dt < zt / 2,
      unknown: zt === 0,
      detail: `跌停 ${dt} 家（需≤20家且少于涨停一半）`,
    },
  ]

  const met = checks.filter((c) => c.met).length
  const unknown = checks.filter((c) => c.unknown).length
  const now = new Date()
  const hhmm = now.getHours() * 100 + now.getMinutes()
  const after1430 = hhmm >= 1430
  let summary
  let cls
  if (unknown >= 2 && met < 3) {
    summary = '⚠️ 数据不足：涨停池/指数K线未取到，先人工核对'
    cls = 'unknown'
  } else if (met === checks.length) {
    summary = '✅ 确认：主升第一天（尾盘14:30后条件保持，可考虑进攻）'
    cls = 'met'
  } else if (met >= 4 && after1430) {
    summary = `✅ 疑似确认：已满足 ${met}/${checks.length} 项，尾盘保持即确认`
    cls = 'met'
  } else if (met >= 4) {
    summary = `🟡 疑似：已满足 ${met}/${checks.length} 项，14:30后再确认`
    cls = 'unknown'
  } else {
    summary = '⛔ 未确认：赚钱效应/量能/梯队不足，不追高'
    cls = 'unmet'
  }
  return { checks, met, total: checks.length, unknown, summary, cls }
}

function _clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n))
}

function _capLabel(cap) {
  if (cap == null || !Number.isFinite(cap)) return '--'
  if (cap <= 0) return '0%'
  if (cap >= 0.8) return '≤80%'
  return `≤${Math.round(cap * 100)}%`
}

/** 市场情绪面板：广度 + 涨停生态（破板/溢价/晋级/回撤）+ 五灯。 */
export function computeSentimentBrief(ctx) {
  const mb = ctx.marketBreadth?.total > 0 ? ctx.marketBreadth : ctx.breadth
  const up = Number(mb?.up) || 0
  const down = Number(mb?.down) || 0
  const flat = Number(mb?.flat) || 0
  const total = Number(mb?.total) || (up + down + flat)
  const upPct = total > 0 ? up / total : null
  const lu = ctx.limitUpStats || {}
  const zt = Number(lu.zt) || 0
  const zb = Number(lu.zb) || 0
  const dt = Number(lu.dt) || 0
  const maxDays = Number(lu.maxDays) || 0
  const breakRate = lu.breakRate != null && Number.isFinite(Number(lu.breakRate))
    ? Number(lu.breakRate)
    : (zt + zb > 0 ? Math.round((zb / (zt + zb)) * 1000) / 10 : null)
  const yestPremium = lu.yestPremium != null && Number.isFinite(Number(lu.yestPremium))
    ? Number(lu.yestPremium)
    : null
  const promoteRate = lu.promoteRate != null && Number.isFinite(Number(lu.promoteRate))
    ? Number(lu.promoteRate)
    : null
  const bigDrawdown = Number(lu.bigDrawdown) || 0
  const lamps = ctx.lamps || computeLamps(ctx)
  const lampRec = positionRecFromLamps(lamps)
  const riskScore = lampRec.riskScore || 0
  const red = lampRec.redCount || 0
  const retreat = sentimentRetreat(ctx.marketBreadth, ctx.breadth)
  const conditions = computeConditions(ctx)
  const condMet = conditions.filter((c) => c.met === true).length
  const condKnown = conditions.filter((c) => c.met !== null && c.met !== undefined).length
  const cycle = computeEmotionCycle(ctx)

  let temp = 48
  if (upPct != null) temp += (upPct - 0.5) * 55
  temp += _clamp(zt / 5, 0, 14)
  if (maxDays >= 5) temp += 8
  else if (maxDays >= 3) temp += 4
  if (dt > 40) temp -= 10
  else if (dt > 20) temp -= 5
  if (breakRate != null) {
    if (breakRate >= 45) temp -= 10
    else if (breakRate >= 30) temp -= 5
    else if (breakRate <= 15 && zt >= 20) temp += 4
  }
  if (yestPremium != null) {
    temp += _clamp(yestPremium * 1.8, -12, 12)
  }
  if (promoteRate != null) {
    if (promoteRate >= 35) temp += 6
    else if (promoteRate >= 20) temp += 3
    else if (promoteRate < 10) temp -= 6
  }
  if (bigDrawdown >= 25) temp -= 10
  else if (bigDrawdown >= 12) temp -= 5
  if (retreat) temp -= 18
  temp -= Math.min(18, riskScore * 4)
  temp = Math.round(_clamp(temp, 0, 100))

  let phase = '均衡'
  let phaseClass = 'neutral'
  if (retreat) {
    phase = '情绪退潮'
    phaseClass = 'cold'
  } else if (temp >= 78 || (zt >= 80 && maxDays >= 4 && (yestPremium == null || yestPremium > 0))) {
    phase = '偏热/亢奋'
    phaseClass = 'hot'
  } else if (temp >= 62) {
    phase = '偏暖'
    phaseClass = 'warm'
  } else if (temp <= 35 || riskScore >= 2.5 || (yestPremium != null && yestPremium < -2 && breakRate >= 35)) {
    phase = '谨慎'
    phaseClass = 'cold'
  }

  const rawLadder = lu.ladder && typeof lu.ladder === 'object' ? lu.ladder : {}
  const ladderKeys = ['1', '2', '3', '4', '5+']
  const ladder = ladderKeys
    .map((k) => ({
      key: k,
      label: k === '1' ? '首板' : k === '5+' ? '5连+' : `${k}连板`,
      count: Number(rawLadder[k]) || 0,
    }))
    .filter((x) => x.count > 0 || ['1', '2', '3'].includes(x.key))

  const volume = computeVolumeBrief(ctx)
  const effects = [
    {
      key: 'volume',
      label: '上证量能',
      value: volume.state === 'unknown'
        ? '--'
        : `${volume.label}${volume.liangbi != null ? ` ${volume.liangbi}` : ''}`,
      tone: volume.state === 'expand' || volume.state === 'mild' ? 'good' : volume.state === 'shrink' ? 'bad' : '',
      tip: volume.tip,
    },
    {
      key: 'amt',
      label: '上证成交额',
      value: volume.amountText || '--',
      tone: '',
      tip: '上证市场成交额；三市合计与较上日此时见顶部「三市」',
    },
    {
      key: 'break',
      label: '破板率',
      value: breakRate != null ? `${breakRate.toFixed(1)}%` : '--',
      tone: breakRate == null ? '' : breakRate >= 35 ? 'bad' : breakRate <= 18 ? 'good' : '',
      tip: '炸板/(涨停+炸板)；越高打板容错越差',
    },
    {
      key: 'premium',
      label: '昨涨停溢价',
      value: yestPremium != null ? `${yestPremium > 0 ? '+' : ''}${yestPremium.toFixed(2)}%` : '--',
      tone: yestPremium == null ? '' : yestPremium >= 1 ? 'good' : yestPremium <= -1 ? 'bad' : '',
      tip: `昨涨停池今日均涨跌（样本 ${Number(lu.yestPremiumSample) || 0}）`,
    },
    {
      key: 'promote',
      label: '连板晋级',
      value: promoteRate != null
        ? `${promoteRate.toFixed(1)}%（${Number(lu.promoteSuccess) || 0}/${Number(lu.promoteEligible) || 0}）`
        : '--',
      tone: promoteRate == null ? '' : promoteRate >= 25 ? 'good' : promoteRate < 12 ? 'bad' : '',
      tip: '昨日涨停今日仍晋级连板的占比',
    },
    {
      key: 'drawdown',
      label: '大幅回撤',
      value: `${bigDrawdown} 家`,
      tone: bigDrawdown >= 15 ? 'bad' : bigDrawdown <= 5 ? 'good' : '',
      tip: `昨涨停今跌≤${Number(lu.bigDrawdownThr) || -5}% 的家数（亏钱效应）`,
    },
    {
      key: 'vsYest',
      label: '较昨量',
      value: volume.vsYestPct,
      tone: volume.vsYest == null ? '' : volume.vsYest >= 1.1 ? 'good' : volume.vsYest < 0.9 ? 'bad' : '',
      tip: '上证今日量/昨全日量；盘中未走完会偏低，宜与量比一起看',
    },
  ]

  return {
    phase,
    phaseClass,
    temp,
    up,
    down,
    flat,
    total,
    upPct: upPct != null ? Math.round(upPct * 1000) / 10 : null,
    zt,
    zb,
    dt,
    maxDays,
    breakRate,
    yestPremium,
    promoteRate,
    bigDrawdown,
    topSector: lu.topSector || '',
    ladder,
    effects,
    volume,
    red,
    riskScore,
    retreat: !!retreat,
    conditions,
    condMet,
    condKnown,
    cycle,
    formula: '温度≈广度+涨停生态−破板/回撤−五灯风险分−退潮（自家口径）',
  }
}

/** 今日操作建议：主线状态 + 自选重合（不直接喊买入）。 */
export function sectorMatch(itemSector, eastName) {
  const a = String(itemSector || '').trim()
  const b = String(eastName || '').trim()
  if (!a || !b || a === '其他') return false
  if (b.includes(a) || a.includes(b)) return true
  const keys = sectorFocusKeywords(a)
  return keys.some((k) => k.length >= 2 && (b.includes(k) || k.includes(b)))
}

function focusAccel(row) {
  const d5 = Number(row?.delta5m)
  const d15 = Number(row?.delta15m)
  const pace = row?.pace || ''
  if (pace === 'in_accel' || (Number.isFinite(d5) && d5 > 0.05)) return 'accelerating'
  if (pace === 'in_decel' || (Number.isFinite(d5) && d5 < -0.05)) return 'fading'
  if (Number.isFinite(d15) && d15 < -0.3 && !(Number.isFinite(d5) && d5 > 0)) return 'fading'
  return 'holding'
}

function focusAccelLabel(kind) {
  if (kind === 'accelerating') return '仍在加速'
  if (kind === 'fading') return '力度转弱'
  return '流入持稳'
}

function toFocusLine(r) {
  const accel = focusAccel(r)
  return {
    name: r.sectorName,
    strength: r.strength,
    netInflow: r.netInflow,
    delta5m: r.delta5m,
    accel,
    accelLabel: focusAccelLabel(accel),
    status: accel === 'accelerating' ? '确认中' : accel === 'fading' ? '偏晚/减弱' : '观察',
  }
}

export function computeDailyAdvice(ctx, sectorFlow) {
  const sentiment = computeSentimentBrief(ctx)
  const rec = effectivePositionRec({ ...ctx, lamps: ctx.lamps || computeLamps(ctx) })
  const sf = sectorFlow || {}
  const summary = sf.summary || {}
  const list = sf.list || []
  const byStrength = [...list]
    .filter((r) => Number(r.strength) || Number(r.netInflow))
    .sort((a, b) => (Number(b.strength) || 0) - (Number(a.strength) || 0))

  // 展示主线：强度 Top3；重合判定：扩到 Top8，减少「明明相关却暂无重合」
  const focusRows = byStrength.slice(0, 3)
  if (!focusRows.length && summary.topStrengthSector) {
    focusRows.push({
      sectorName: summary.topStrengthSector,
      strength: summary.topStrength,
      netInflow: summary.topNetInflow,
    })
  }
  const matchRows = byStrength.slice(0, 8)
  if (!matchRows.length && focusRows.length) matchRows.push(...focusRows)

  const focuses = focusRows.map((r) => r.sectorName).filter(Boolean)
  const focusLines = focusRows.filter((r) => r.sectorName).map(toFocusLine)
  const matchLines = matchRows.filter((r) => r.sectorName).map(toFocusLine)

  const watchHits = []
  const items = ctx.items || []
  const quotes = ctx.quotes || {}
  const klines = ctx.klines || {}
  const positions = ctx.positions || {}
  const analyses = ctx.analyses || {}
  const staleDays = ctx.staleDays
  for (const it of items) {
    const hitFocus = matchLines.find((f) => sectorMatch(it.sector || getSector(it.code), f.name))
    if (!hitFocus) continue
    const q = quotes[it.code] || {}
    const k = klines[it.code] || {}
    const a = analyses[it.code] || {}
    const rating = effectiveRating(it, ctx)
    const riskCleared = isRiskCleared(a, staleDays)
    const belowMA20 = k.ma20 > 0 && q.price > 0 && q.price < k.ma20
    const inPos = !!positions[it.code]
    let action = '主线重合·观察'
    let actionTone = 'watch'
    let priority = 2
    if (!rec.buyAllowed) {
      action = '主线重合·总仓不允许新开'
      actionTone = 'block'
      priority = 4
    } else if (belowMA20) {
      action = '主线重合·破MA20不追'
      actionTone = 'block'
      priority = 3
    } else if (rating === '可买入' && riskCleared && hitFocus.accel !== 'fading') {
      action = '主线重合·过门禁可考虑'
      actionTone = 'ready'
      priority = 0
    } else if (rating === '可买入' && !riskCleared) {
      action = '主线重合·先过利空门禁'
      actionTone = 'gate'
      priority = 1
    } else if (inPos) {
      action = '主线重合·持仓关注'
      actionTone = 'hold'
      priority = 1
    } else if (hitFocus.accel === 'fading') {
      action = '主线重合·力度转弱宜谨慎'
      actionTone = 'fade'
      priority = 3
    }
    watchHits.push({
      code: it.code,
      rawCode: String(it.code || '').replace(/^(sh|sz)/i, ''),
      name: it.name || q.name || it.code,
      sector: it.sector || getSector(it.code),
      focusName: hitFocus.name,
      accel: hitFocus.accel,
      rating,
      riskCleared,
      belowMA20,
      inPosition: inPos,
      price: q.price,
      changePct: q.changePct,
      action,
      actionTone,
      priority,
    })
  }
  watchHits.sort((a, b) => a.priority - b.priority || (b.changePct || 0) - (a.changePct || 0))

  let style = '观察为主'
  if (!rec.buyAllowed || rec.cap <= 0) style = '只卖不买'
  else if (sentiment.retreat) style = '只卖不买'
  else if (sentiment.cycle?.id === 'climax' || sentiment.phaseClass === 'hot') style = '控仓忌追'
  else if (focusLines.some((f) => f.accel === 'accelerating') && rec.cap >= 0.5) style = '主线加速·控节奏'
  else if (sentiment.cycle?.id === 'ferment' || (sentiment.phaseClass === 'warm' && rec.cap >= 0.5)) style = '快进快出'
  else if (rec.cap >= 0.5) style = '控节奏参与'
  else style = '轻仓试错'

  let risk = ''
  if (!rec.buyAllowed) risk = '不宜新开仓'
  else if (sentiment.cycle?.id === 'diverge') risk = '情绪分歧防回撤'
  else if (sentiment.yestPremium != null && sentiment.yestPremium < -1.5 && (sentiment.breakRate || 0) >= 30) {
    risk = '溢价差+破板高'
  } else if (sentiment.condKnown && sentiment.condMet < 2) risk = '四条件偏弱'
  else if (sentiment.cycle?.id === 'climax' || sentiment.phaseClass === 'hot') risk = '防高潮回撤'
  else if (rec.riskScore > 0) risk = `五灯风险${rec.riskScore}`

  const focusText = focuses.length ? focuses.slice(0, 2).join(' / ') : '待确认'
  const readyN = watchHits.filter((h) => h.actionTone === 'ready').length
  const cycleLabel = sentiment.cycle?.label || '--'
  const headline = `${rec.buyAllowed === false ? '禁开仓' : '可参与'} · ${_capLabel(rec.cap)} · ${style}`

  return {
    positionText: _capLabel(rec.cap),
    positionLevel: rec.level,
    style,
    focuses,
    focusText,
    focusLines,
    watchHits,
    watchHitCount: watchHits.length,
    readyCount: readyN,
    headline,
    cycle: sentiment.cycle || null,
    metrics: [
      { key: 'cap', label: '仓位', value: _capLabel(rec.cap), tone: rec.level },
      {
        key: 'cycle',
        label: '情绪阶段',
        value: cycleLabel,
        tone: sentiment.cycle?.id === 'retreat' || sentiment.cycle?.id === 'climax'
          ? 'warn'
          : sentiment.cycle?.id === 'ferment' ? 'focus' : '',
      },
      { key: 'style', label: '风格', value: style, tone: '' },
      { key: 'focus', label: '主线', value: focusText, tone: focuses.length ? 'focus' : '' },
      {
        key: 'map',
        label: '自选重合',
        value: watchHits.length
          ? `${watchHits.length}只${readyN ? `·${readyN}过门禁` : ''}`
          : '暂无',
        tone: readyN ? 'ready' : watchHits.length ? 'watch' : '',
      },
    ],
    rationale: headline,
    risk,
    buyAllowed: !!rec.buyAllowed,
    redCount: rec.redCount,
    riskScore: rec.riskScore,
    detail: rec.detail || '',
    note: `情绪阶段「${cycleLabel}」为环境输入；主线=资金强度 Top3，重合对照强度 Top8；重合≠买入指令。`,
  }
}

/** 自选一句话理由：门禁 > 人工备注 > 评分拼装（预警另有提醒列，不在此重复）。 */
export function buildCardReason(card) {
  if (card?.gateBlocked) {
    if (card.rating === '不追') return '评分达可买入，偏离MA20>5% 降为不追'
    if (!card.riskCleared) return '评分达可买入，利空门禁仍拦截为观察'
    return '评分达可买入，五灯/量比等门禁仍拦截为观察'
  }
  if (card?.reason) return String(card.reason)
  const bits = []
  if (card?.liveScore != null || (card?.score != null && card.score > 0)) {
    bits.push(`综合分 ${card.score}`)
  }
  if (card?.rating) bits.push(card.rating)
  if (card?.belowMA20) bits.push('破MA20')
  if (card?.pos && Number.isFinite(card.pnlPct)) {
    bits.push(`持仓 ${card.pnlPct >= 0 ? '+' : ''}${card.pnlPct.toFixed(1)}%`)
  }
  if (card?.sector && card.sector !== '其他') bits.push(card.sector)
  if (card?.stale) bits.push('分析待更新')
  return bits.length ? bits.join(' · ') : '—'
}
