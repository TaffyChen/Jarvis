export const SECTOR_MAP = {
  '002463': 'PCB', '002916': 'PCB', '300502': 'CPO/光模块', '300408': 'MLCC', '002156': '先进封装',
  '600584': '先进封装', '300604': '半导体设备', '002371': '半导体设备', '002409': '半导体材料',
  '301308': '存储', '603986': '存储', '300480': '半导体', '300394': 'CPO/光模块', '000636': 'MLCC',
  '300308': 'CPO/光模块', '688256': 'AI芯片', '688041': 'AI芯片', '688981': '半导体制造',
  '603629': '算力租赁', '000815': '算力租赁', '300442': 'IDC', '301396': '算力租赁', '600536': '信创',
  '515050': '通信', '513310': '半导体', '562500': '机器人', '562590': '半导体', '159300': '宽基',
  '588000': '宽基', '159659': '海外', '513090': '券商', '159740': '港股科技', '513330': '港股互联网',
  '515220': '煤炭/红利', '159330': '宽基', '000333': '消费', '002230': 'AI/软件', '600588': 'AI/软件',
  '000899': '电力', '000923': '资源', '300033': '金融科技', '002131': '其他',
}

export function getSector(code) {
  const raw = String(code || '').replace(/^(sh|sz)/i, '')
  return SECTOR_MAP[raw] || '其他'
}

export const ANALYSIS_STALE_DAYS = 14
export const OVERSEAS_SPX_RED = -1.5
export const OVERSEAS_QQQ_RED = -2.0

export function liveScoreFrom(q, k) {
  if (!q || q.price <= 0 || !k || (k.ma20 <= 0 && typeof k.change20d !== 'number')) return null
  let s = 0
  const pe = q.peTTM > 0 ? q.peTTM : (q.pe > 0 ? q.pe : 0)
  if (pe > 0 && pe < 30) s += 25
  else if (pe > 0 && pe < 50) s += 20
  else if (pe > 0 && pe < 80) s += 15
  else if (pe > 0 && pe < 150) s += 10
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

export function ratingFromScore(score) {
  if (score >= 60) return '可买入'
  if (score >= 40) return '观察'
  if (score >= 20) return '不追'
  return '排除'
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
