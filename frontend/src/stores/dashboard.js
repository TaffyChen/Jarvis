import { defineStore } from 'pinia'
import { api } from '../api'
import {
  ANALYSIS_STALE_DAYS,
  getSector,
  isAnalysisStale,
  isRiskCleared,
  liveScoreFrom,
  makeSparkline,
  ratingClassOf,
} from '../utils/strategy'
import { matchStockQuery, pinyinFull, pinyinInitials } from '../utils/match'
import {
  computeAlerts,
  computeConditions,
  computeLamps,
  computeMainRise,
  computeSentimentBrief,
  computeDailyAdvice,
  computeVolumePhase,
  buildCardReason,
  effectiveRating,
  effectivePositionRec,
  positionRiskLevels,
  maxHighSinceBuy,
  isStrongTrend,
  toggleLeverOverride,
  toggleMainRiseIce,
} from '../utils/signals'

/** 会话级 UI 状态（F5 不丢当前页/搜索/板块/对话开关；定时刷新不碰这些字段） */
const UI_STATE_KEY = 'jarvis-ui-state'
const UI_VIEWS = new Set([
  'market', 'stocks', 'sectorFlow', 'screen', 'auction', 'journal', 'review', 'knowledge',
])

function loadUiState() {
  try {
    const raw = sessionStorage.getItem(UI_STATE_KEY)
    if (!raw) return {}
    const o = JSON.parse(raw)
    return o && typeof o === 'object' ? o : {}
  } catch {
    return {}
  }
}

export function persistUiState(partial) {
  try {
    const prev = loadUiState()
    sessionStorage.setItem(UI_STATE_KEY, JSON.stringify({ ...prev, ...partial }))
  } catch {
    /* ignore */
  }
}

const _ui = loadUiState()

function itemFromCode(code, quotes, analyses, positions) {
  const q = quotes?.[code] || {}
  const a = analyses?.[code] || {}
  const pos = positions?.[code]
  const isEtf = /^(sh5|sz1)/i.test(code) || a.type === 'etf'
  const name = q.name || a.name || pos?.name || code
  return {
    code,
    rawCode: code.replace(/^(sh|sz)/i, ''),
    name,
    pyInitials: pinyinInitials(name),
    pyFull: pinyinFull(name),
    type: isEtf ? 'etf' : 'stock',
    rating: a.ratingManual === '排除' ? '排除' : (a.rating || null),
    autoRating: true,
    reason: a.reason || '',
    notes: a.notes || '',
    analysis: a.analysis || [],
    etf: a.etf || null,
    riskOk: a.riskOk,
    reviewedAt: a.reviewedAt,
    sector: getSector(code),
    industry: (quotes?.[code] || {}).industry || '',
  }
}

function buildItems(quotes, analyses, positions) {
  const codes = new Set([
    ...Object.keys(quotes || {}),
    ...Object.keys(analyses || {}),
    ...Object.keys(positions || {}),
  ])
  return [...codes].map((code) => itemFromCode(code, quotes, analyses, positions))
}

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    quotes: {},
    indices: {},
    marketTurnover: {
      amountYi: null,
      deltaYi: null,
      ready: false,
      source: '',
      note: '',
    },
    sentimentHistory: {
      day: null,
      temp: null,
      iceBand: 35,
      boilBand: 78,
      range: '1m',
      rangeLabel: '近一月',
      points: [],
      heightPoints: [],
      note: '',
    },
    klines: {},
    positions: {},
    analyses: {},
    journal: [],
    breadth: { up: 0, down: 0, flat: 0, total: 0 },
    marketBreadth: { up: 0, down: 0, flat: 0, total: 0, source: '' },
    overseas: null,
    limitUpStats: {
      zt: 0, zb: 0, dt: 0, maxDays: 0, topSector: '', ladder: {},
      breakRate: null, yestPremium: null, promoteRate: null, bigDrawdown: 0, yestLoss: 0, source: '',
    },
    lastUpdate: null,
    staleDays: ANALYSIS_STALE_DAYS,
    health: null,
    loading: false,
    error: '',
    filter: ['all', 'buy', 'watch', 'nochase', 'hold', 'exclude'].includes(_ui.filter) ? _ui.filter : 'all',
    sector: typeof _ui.sector === 'string' && _ui.sector ? _ui.sector : 'all',
    search: typeof _ui.search === 'string' ? _ui.search : '',
    view: UI_VIEWS.has(_ui.view) ? _ui.view : 'market',
    chatOpen: !!_ui.chatOpen,
    strategyOpen: false,
    positionOpen: false,
    addOpen: false,
    signalTick: 0,
    screenResults: [],
    screenTrendResults: [],
    screenMeta: null,
    screenLoading: false,
    auctionResults: [],
    auctionMeta: null,
    auctionLoading: false,
    sectorFlow: {
      summary: {
        totalNetInflow: 0,
        positiveCount: 0,
        negativeCount: 0,
        total: 0,
        divergenceCount: 0,
        topSector: null,
        topNetInflow: 0,
        topChangePct: 0,
        topStrengthSector: null,
        topStrength: 0,
        bottomSector: null,
        bottomNetInflow: 0,
        bottomChangePct: 0,
      },
      list: [],
      source: '',
      disclaimer: '',
      lastUpdate: null,
    },
  }),
  getters: {
    items(state) {
      return buildItems(state.quotes, state.analyses, state.positions)
    },
    ctx(state) {
      // signalTick forces recompute after localStorage toggles
      void state.signalTick
      return {
        items: buildItems(state.quotes, state.analyses, state.positions),
        quotes: state.quotes,
        klines: state.klines,
        positions: state.positions,
        analyses: state.analyses,
        marketBreadth: state.marketBreadth,
        breadth: state.breadth,
        overseas: state.overseas,
        limitUpStats: state.limitUpStats,
        indices: state.indices,
        staleDays: state.staleDays,
      }
    },
    conditions() {
      return computeConditions(this.ctx)
    },
    lamps() {
      return computeLamps(this.ctx)
    },
    positionRec() {
      return effectivePositionRec(this.ctx)
    },
    sentimentBrief() {
      return computeSentimentBrief({ ...this.ctx, lamps: this.lamps })
    },
    dailyAdvice() {
      return computeDailyAdvice({ ...this.ctx, lamps: this.lamps }, this.sectorFlow)
    },
    alerts() {
      return computeAlerts(this.ctx)
    },
    mainRise() {
      return computeMainRise(this.ctx)
    },
    tabCounts() {
      const counts = { all: 0, buy: 0, watch: 0, nochase: 0, hold: 0, exclude: 0 }
      // 持仓角标与「持仓管理」对齐：直接数 positions，不依赖观察池条目是否齐全
      counts.hold = Object.keys(this.positions || {}).length
      this.items.forEach((item) => {
        counts.all++
        const rating = effectiveRating(item, this.ctx)
        if (rating === '可买入') counts.buy++
        if (rating === '观察' || rating === '持仓') counts.watch++
        if (rating === '不追' || rating === '不买') counts.nochase++
        if (rating === '排除') counts.exclude++
      })
      return counts
    },
    sectors() {
      const map = {}
      this.items.forEach((i) => {
        map[i.sector] = (map[i.sector] || 0) + 1
      })
      return Object.keys(map).sort().map((s) => ({ name: s, count: map[s] }))
    },
    cards() {
      const ctx = this.ctx
      // 持仓 Tab：以 positions 为源，避免观察池/行情缺码时漏掉（与持仓管理一致）
      const sourceItems = this.filter === 'hold'
        ? Object.keys(this.positions || {}).map((code) =>
          itemFromCode(code, this.quotes, this.analyses, this.positions))
        : this.items
      let list = sourceItems.map((item) => {
        const q = this.quotes[item.code] || {}
        const k = this.klines[item.code] || {}
        const a = this.analyses[item.code] || {}
        const pos = this.positions[item.code]
        const score = liveScoreFrom(q, k, {
          code: item.code,
          sector: item.sector,
          industry: q.industry || item.industry || '',
        })
        const rating = effectiveRating(item, ctx)
        const displayScore = score != null ? score : 0
        const stale = isAnalysisStale(a, this.staleDays)
        const riskCleared = isRiskCleared(a, this.staleDays)
        const belowMA20 = k.ma20 > 0 && q.price > 0 && q.price < k.ma20
        const cardAlerts = this.alerts.filter((x) => x.code === item.code)
        const primaryAlert = cardAlerts[0] || null
        let pnl = 0
        let pnlPct = 0
        if (pos && q.price > 0) {
          pnl = (q.price - pos.buyPrice) * pos.shares
          pnlPct = pos.buyPrice > 0 ? (q.price - pos.buyPrice) / pos.buyPrice * 100 : 0
        }
        const levels = pos ? positionRiskLevels(pos, q.price, {
          code: item.code,
          name: item.name,
          maxHigh: maxHighSinceBuy(k, pos) || q.price,
          strongTrend: isStrongTrend(k),
        }) : null
        const rawScoreRating = score != null ? (score >= 60 ? '可买入' : null) : null
        const base = {
          ...item,
          q,
          k,
          a,
          pos,
          score: displayScore,
          liveScore: score,
          rating,
          ratingClass: ratingClassOf(rating),
          stale,
          riskCleared,
          belowMA20,
          sparkHtml: makeSparkline(k.sparkline || []),
          cardAlerts,
          primaryAlert,
          levels,
          pnl,
          pnlPct,
          gateBlocked: rawScoreRating === '可买入' && (rating === '观察' || rating === '不追'),
          gateReason: rawScoreRating === '可买入' && rating !== '可买入'
            ? (rating === '不追' ? '偏离门禁' : '门禁拦截')
            : '',
        }
        const hit = (this.dailyAdvice?.watchHits || []).find((h) => h.code === item.code)
        const volumePhase = computeVolumePhase(q, k)
        return {
          ...base,
          reasonLine: buildCardReason(base),
          mainlineHit: hit || null,
          mainlineTone: hit?.actionTone || '',
          mainlineAction: hit?.action || '',
          volumePhase,
        }
      })

      list = list.filter((c) => {
        if (this.filter === 'hold') return !!c.pos
        if (this.filter === 'buy') return c.rating === '可买入'
        if (this.filter === 'watch') return c.rating === '观察' || c.rating === '持仓'
        if (this.filter === 'nochase') return c.rating === '不追' || c.rating === '不买'
        if (this.filter === 'exclude') return c.rating === '排除'
        return true
      })
      const q = String(this.search || '').trim()
      // 有搜索词时不套板块 chip，避免「chip 停在 PCB 时搜半导体」被误滤空
      if (this.filter !== 'hold' && this.sector !== 'all' && !q) {
        list = list.filter((c) => c.sector === this.sector)
      }
      if (q) {
        list = list.filter((c) => matchStockQuery(c, q))
      }
      list.sort((a, b) => {
        const pa = a.mainlineTone === 'ready' ? 2 : a.mainlineHit ? 1 : 0
        const pb = b.mainlineTone === 'ready' ? 2 : b.mainlineHit ? 1 : 0
        if (pb !== pa) return pb - pa
        return b.score - a.score
      })
      return list
    },
  },
    actions: {
    async refreshMarket({ quiet = false } = {}) {
      if (!quiet) {
        this.loading = true
        this.error = ''
      }
      try {
        const [q, m, k, sf] = await Promise.all([
          api.quotes(),
          api.market(),
          api.klines(),
          api.sectorFlow().catch(() => null),
        ])
        this.quotes = q.quotes || {}
        this.breadth = q.breadth || this.breadth
        this.marketBreadth = q.marketBreadth || this.marketBreadth
        this.overseas = q.overseas
        this.limitUpStats = q.limitUpStats || this.limitUpStats
        this.lastUpdate = q.lastUpdate
        this.indices = m.indices || {}
        this.marketTurnover = m.marketTurnover || q.marketTurnover || this.marketTurnover
        this.sentimentHistory = q.sentimentHistory || m.sentimentHistory || this.sentimentHistory
        this.klines = k.klines || {}
        if (sf && Array.isArray(sf.list)) this.sectorFlow = sf
      } catch (e) {
        if (!quiet) this.error = e.message || '加载失败，请确认后端已启动'
      } finally {
        if (!quiet) this.loading = false
      }
    },
    async refreshBusiness({ quiet = false } = {}) {
      try {
        const [h, p, a, j] = await Promise.all([
          api.health().catch(() => null),
          api.positions(),
          api.analyses(),
          api.journal().catch(() => ({ journal: [] })),
        ])
        this.health = h
        this.positions = p.positions || {}
        this.analyses = a.analyses || {}
        if (a.staleDays) this.staleDays = a.staleDays
        this.journal = j.journal || []
      } catch (e) {
        if (!quiet) this.error = e.message || '业务数据加载失败'
      }
    },
    async refresh() {
      this.loading = true
      this.error = ''
      try {
        await Promise.all([
          this.refreshMarket({ quiet: true }),
          this.refreshBusiness({ quiet: true }),
        ])
      } catch (e) {
        this.error = e.message || '加载失败，请确认后端已启动'
      } finally {
        this.loading = false
      }
    },
    async savePositions(next) {
      this.positions = next
      await api.savePositions(next)
      await this.refresh()
    },
    async reviewAnalysis(code, riskOk, notes) {
      const prev = this.analyses[code] || { code, name: this.quotes[code]?.name || code }
      await api.upsertAnalysis({
        ...prev,
        code,
        riskOk,
        notes: notes != null ? notes : (prev.notes || ''),
        reviewedAt: new Date().toISOString().slice(0, 10),
        ratingManual: riskOk === false ? (prev.ratingManual || null) : null,
      })
      await this.refresh()
    },
    async journalAlert(alert, note = '') {
      await api.addJournal({
        ts: new Date().toISOString(),
        code: alert.code,
        name: alert.name,
        level: alert.level,
        msg: alert.msg,
        action: alert.action,
        note,
        lamps: this.positionRec.redCount,
      })
      await this.refresh()
    },
    flipLever() {
      toggleLeverOverride()
      this.signalTick++
    },
    flipIce() {
      toggleMainRiseIce()
      this.signalTick++
    },
    async fetchScreen() {
      this.screenLoading = true
      try {
        const r = await api.screen()
        this.screenResults = r.results || []
        this.screenTrendResults = r.trendResults || []
        this.screenMeta = r
      } finally {
        this.screenLoading = false
      }
    },
    async fetchAuction() {
      this.auctionLoading = true
      try {
        const r = await api.auction()
        this.auctionResults = r.results || []
        this.auctionMeta = r
      } finally {
        this.auctionLoading = false
      }
    },
    async addStock(payload) {
      const { code, analysis } = payload
      if (code) await api.addCodes([code])
      if (analysis) await api.upsertAnalysis(analysis)
      await this.refresh()
    },
    async removeStock(code) {
      await api.removeCodes([code])
      const nextA = { ...this.analyses }
      delete nextA[code]
      await api.upsertAnalysis({ analyses: nextA })
      await this.refresh()
    },
  },
})
