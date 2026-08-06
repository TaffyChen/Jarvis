import {
  OVERSEAS_QQQ_RED,
  OVERSEAS_SPX_RED,
  getSector,
  isRiskCleared,
  liveScoreFrom,
  ratingFromScore,
} from './strategy'

const STOP_LOSS_PCT = -8
const PROFIT_TAKE_PCT = 10
const PROFIT_GREEN_PCT = 3
const PROFIT_GREEN_CONFIRM_PCT = 1.5
const DRAWDOWN_ALERT_PCT = 3
const HIGH_60D_PCT = 50
const BIG_DROP_PCT = -5
const LEVER_KEY = 'jarvis_lever5_override'
const MAIN_RISE_ICE_KEY = 'jarvis_main_rise_ice'

export { STOP_LOSS_PCT, PROFIT_TAKE_PCT }

/**
 * 持仓止损/止盈参考价。
 * 有自定义价则用自定义；否则按全局比例（成本 -8% / +10%）自动算。
 * 规则仍是主裁判；价格是辅助触发与展示。
 */
export function positionRiskLevels(pos, price) {
  const buy = Number(pos?.buyPrice) || 0
  if (!(buy > 0)) return null
  const customSl = Number(pos?.stopLossPrice)
  const customTp = Number(pos?.takeProfitPrice)
  const hasCustomSl = Number.isFinite(customSl) && customSl > 0
  const hasCustomTp = Number.isFinite(customTp) && customTp > 0
  const autoStopLoss = buy * (1 + STOP_LOSS_PCT / 100)
  const autoTakeProfit = buy * (1 + PROFIT_TAKE_PCT / 100)
  const stopLoss = hasCustomSl ? customSl : autoStopLoss
  const takeProfit = hasCustomTp ? customTp : autoTakeProfit
  const p = Number(price) || 0
  return {
    stopLoss,
    takeProfit,
    stopLossSource: hasCustomSl ? 'custom' : 'auto',
    takeProfitSource: hasCustomTp ? 'custom' : 'auto',
    autoStopLoss,
    autoTakeProfit,
    distToStopPct: p > 0 ? ((p - stopLoss) / stopLoss) * 100 : null,
    distToTakePct: p > 0 ? ((takeProfit - p) / p) * 100 : null,
    stopHit: p > 0 && p <= stopLoss,
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
  return (m === 1 && day >= 17 && day <= 31) || (m === 7 && day >= 1 && day <= 15)
}

function maxHighSinceBuy(k, pos) {
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

function limitDownPct(code, name) {
  code = String(code || '').replace(/^(sh|sz)/, '')
  if (/^(300|301|688)/.test(code)) return -19.9
  if (String(name || '').includes('ST')) return -4.9
  return -9.9
}

export function computeConditions({ items, quotes, klines, marketBreadth, breadth }) {
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
  let volExpanded = 0
  let volTotal = 0
  stockItems.forEach((i) => {
    const k = klines[i.code]
    const q = quotes[i.code]
    if (k?.klines?.length >= 2 && q?.volume > 0) {
      volTotal++
      const yest = k.klines[k.klines.length - 2].volume
      if (q.volume > yest) volExpanded++
    }
  })
  const cond4 = volTotal ? volExpanded / volTotal > 0.5 : null
  return [
    { name: '高开不回落', met: cond1 },
    { name: '上涨>6成', met: cond2 },
    { name: '科技翻红', met: cond3 },
    { name: '放量', met: cond4 },
  ]
}

export function computeLamps({ items, quotes, klines, positions, overseas }) {
  const lamps = []
  const stockItems = items.filter((i) => i.type !== 'etf')
  const withTurnover = stockItems.filter((i) => quotes[i.code]?.turnover > 0)
  const avgTurnover = withTurnover.length
    ? withTurnover.reduce((s, i) => s + quotes[i.code].turnover, 0) / withTurnover.length
    : 0
  lamps.push({
    name: '换手拥挤(自选)',
    red: avgTurnover > 10,
    detail: avgTurnover > 0 ? `自选平均换手率${avgTurnover.toFixed(2)}%（>10%红灯）` : '数据不足',
  })
  const lever = getLeverOverride()
  lamps.push({
    name: '杠杆5连降',
    red: lever,
    manual: true,
    detail: lever ? '已手动标记：两融连续5日下降' : '未标记；点击可手动切换',
  })
  const earn = isEarningsWindow()
  lamps.push({
    name: '业绩验证期',
    red: earn,
    detail: earn ? '当前处于业绩验证窗口' : '非业绩验证窗口',
  })
  const nas = quotes.sz159659
  const lamp4 = !!(overseas && overseas.changePct <= OVERSEAS_SPX_RED) || !!(nas && nas.changePct <= OVERSEAS_QQQ_RED)
  let od = overseas ? `标普日跌 ${overseas.changePct.toFixed(2)}%` : ''
  if (nas) od += `${od ? ' | ' : ''}纳指ETF ${nas.changePct.toFixed(2)}%`
  lamps.push({ name: '海外隔夜大跌', red: lamp4, detail: od || '海外数据不足' })

  const held = Object.keys(positions || {})
  let below = 0
  let withMA = 0
  held.forEach((fc) => {
    const k = klines[fc]
    const q = quotes[fc]
    if (k?.ma20 > 0 && q?.price > 0) {
      withMA++
      if (q.price < k.ma20) below++
    }
  })
  const pct = withMA ? below / withMA : 0
  lamps.push({
    name: `破20日线(持仓${withMA ? (pct * 100).toFixed(0) : '?'}%)`,
    red: withMA > 0 && pct > 0.5,
    detail: withMA ? `${below}/${withMA}只持仓破20日线` : '数据不足',
  })
  return lamps
}

export function positionRecFromLamps(lamps) {
  const redCount = lamps.filter((l) => l.red).length
  if (redCount >= 4) return { redCount, text: '仓位归零！只卖不买', level: 'danger', lampCap: 0 }
  if (redCount === 3) return { redCount, text: '仓位上限1成', level: 'danger', lampCap: 0.1 }
  if (redCount === 2) return { redCount, text: '仓位上限3成', level: 'warning', lampCap: 0.3 }
  if (redCount === 1) return { redCount, text: '仓位上限5成', level: 'warning', lampCap: 0.5 }
  return { redCount, text: '仓位上限8成', level: 'safe', lampCap: 0.8 }
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
  const redCount = lamps.filter((l) => l.red).length
  if (redCount >= 4) alerts.push({ level: 'danger', code: 'ALL', name: '全部持仓', msg: `五灯${redCount}红！仓位归零`, action: '立即清仓' })
  else if (redCount === 3) alerts.push({ level: 'danger', code: 'ALL', name: '全部持仓', msg: '五灯3红，仓位上限1成', action: '减仓至1成' })

  const retreat = sentimentRetreat(marketBreadth, breadth)
  if (retreat) {
    const lampCap = positionRecFromLamps(lamps).lampCap ?? 0.8
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
    const name = item?.name || fullCode
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
    const belowMA20 = k?.ma20 > 0 && price < k.ma20
    let failedReclaim = false
    if (k?.klines?.length >= 21) {
      const prevMA20 = ma20At(k.klines, k.klines.length - 2)
      const prevBar = k.klines[k.klines.length - 2]
      if (prevBar && prevMA20 > 0 && prevBar.close < prevMA20) failedReclaim = true
    }

    if (belowMA20) {
      if (k.ma60 > 0 && price < k.ma60) {
        alerts.push({ level: 'danger', code: fullCode, name, msg: `跌破20/60日线`, action: '铁律1：清仓' })
      } else if (failedReclaim) {
        alerts.push({ level: 'danger', code: fullCode, name, msg: `昨日已破20日线，今日未站回`, action: '铁律1：清仓' })
      } else {
        alerts.push({ level: 'danger', code: fullCode, name, msg: `今日跌破20日线(${k.ma20.toFixed(2)})`, action: '铁律1：减半仓' })
      }
    }
    if (maxProfitPct >= PROFIT_TAKE_PCT && drawdownFromHigh <= -DRAWDOWN_ALERT_PCT) {
      alerts.push({ level: 'danger', code: fullCode, name, msg: `浮盈曾达${maxProfitPct.toFixed(1)}%，回撤${drawdownFromHigh.toFixed(1)}%`, action: '铁律2：清掉剩余仓位' })
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
    const levels = positionRiskLevels(pos, price)
    if (levels?.takeHit) {
      const src = levels.takeProfitSource === 'custom' ? '自定义止盈' : '止盈线'
      alerts.push({
        level: 'warning',
        code: fullCode,
        name,
        msg: `现价触及${src}(${levels.takeProfit.toFixed(2)})`,
        action: '强制兑现部分',
      })
    } else if (levels?.takeProfitSource === 'auto' && pnlPct >= PROFIT_TAKE_PCT) {
      alerts.push({ level: 'warning', code: fullCode, name, msg: `盈利${pnlPct.toFixed(1)}%达止盈线`, action: '强制兑现部分' })
    }
    if (levels?.stopHit) {
      const src = levels.stopLossSource === 'custom' ? '自定义止损' : '止损线'
      alerts.push({
        level: 'danger',
        code: fullCode,
        name,
        msg: `现价触及${src}(${levels.stopLoss.toFixed(2)})`,
        action: '立即止损卖出',
      })
    } else if (levels?.stopLossSource === 'auto' && drawdownFromHigh <= STOP_LOSS_PCT) {
      alerts.push({ level: 'danger', code: fullCode, name, msg: `自高点回撤触及止损线`, action: '立即止损卖出' })
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

  // dedupe sell alerts per code keep highest priority
  const sellScore = (a) => {
    if (a.action.includes('止损')) return 10
    if (a.action.includes('清仓')) return 9
    if (a.action.includes('立即卖出')) return 8
    if (a.action.includes('清掉剩余')) return 7
    if (a.action.includes('保本')) return 6
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

export function effectiveRating(item, { quotes, klines, positions, analyses, staleDays }) {
  const fc = item.code
  const a = analyses[fc]
  if (positions[fc]) return '持仓'
  if ((a && a.ratingManual === '排除') || (item.rating === '排除' && !item.autoRating)) return '排除'
  const ls = liveScoreFrom(quotes[fc], klines[fc])
  if (ls == null) return item.rating || '观察'
  let raw = ratingFromScore(ls)
  if (raw === '可买入' && !isRiskCleared(a, staleDays)) raw = '观察'
  return raw
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

  let volExpanded = 0
  let volTotal = 0
  stockItems.forEach((i) => {
    const k = klines[i.code]
    const q = quotes[i.code]
    if (k?.klines?.length >= 2 && q?.volume > 0) {
      volTotal++
      if (q.volume > k.klines[k.klines.length - 2].volume) volExpanded++
    }
  })
  const cond4 = volTotal ? volExpanded / volTotal > 0.5 : null

  // 指数量能近似（若无指数K线则用自选放量）
  let ratio = null
  const sh = klines?.sh000001 || indices?.sh000001
  // indices don't have klines here; use cond4 fallback
  void sh
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
      met: ratio != null ? ratio >= 1.1 : cond4 === true,
      unknown: ratio == null && cond4 == null,
      detail: ratio != null
        ? `指数量能较昨日 ${ratio >= 1 ? '+' : ''}${((ratio - 1) * 100).toFixed(1)}%（需≥10%）`
        : (cond4 != null ? `自选放量占比${cond4 ? '达标' : '不足'}（指数K线缺失，用自选近似）` : '量能数据缺失'),
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
