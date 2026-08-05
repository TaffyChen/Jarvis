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
import {
  computeAlerts,
  computeConditions,
  computeLamps,
  computeMainRise,
  effectiveRating,
  positionRecFromLamps,
  toggleLeverOverride,
  toggleMainRiseIce,
} from '../utils/signals'

function buildItems(quotes, analyses, positions) {
  const codes = new Set([
    ...Object.keys(quotes || {}),
    ...Object.keys(analyses || {}),
    ...Object.keys(positions || {}),
  ])
  return [...codes].map((code) => {
    const q = quotes[code] || {}
    const a = analyses[code] || {}
    const isEtf = /^(sh5|sz1)/i.test(code) || a.type === 'etf'
    return {
      code,
      rawCode: code.replace(/^(sh|sz)/i, ''),
      name: q.name || a.name || code,
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
    }
  })
}

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    quotes: {},
    indices: {},
    klines: {},
    positions: {},
    analyses: {},
    journal: [],
    breadth: { up: 0, down: 0, flat: 0, total: 0 },
    marketBreadth: { up: 0, down: 0, flat: 0, total: 0, source: '' },
    overseas: null,
    limitUpStats: { zt: 0, zb: 0, dt: 0, maxDays: 0, topSector: '', source: '' },
    lastUpdate: null,
    staleDays: ANALYSIS_STALE_DAYS,
    health: null,
    loading: false,
    error: '',
    filter: 'all',
    sector: 'all',
    search: '',
    view: 'stocks',
    chatOpen: false,
    strategyOpen: false,
    positionOpen: false,
    addOpen: false,
    signalTick: 0,
    screenResults: [],
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
        topSector: null,
        topNetInflow: 0,
        topChangePct: 0,
        bottomSector: null,
        bottomNetInflow: 0,
        bottomChangePct: 0,
      },
      list: [],
      source: '',
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
      return positionRecFromLamps(this.lamps)
    },
    alerts() {
      return computeAlerts(this.ctx)
    },
    mainRise() {
      return computeMainRise(this.ctx)
    },
    tabCounts() {
      const counts = { all: 0, buy: 0, watch: 0, nochase: 0, hold: 0, exclude: 0 }
      this.items.forEach((item) => {
        counts.all++
        const rating = effectiveRating(item, this.ctx)
        if (this.positions[item.code]) counts.hold++
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
      let list = this.items.map((item) => {
        const q = this.quotes[item.code] || {}
        const k = this.klines[item.code] || {}
        const a = this.analyses[item.code] || {}
        const pos = this.positions[item.code]
        const score = liveScoreFrom(q, k)
        const rating = effectiveRating(item, ctx)
        const displayScore = score != null ? score : 0
        const stale = isAnalysisStale(a, this.staleDays)
        const riskCleared = isRiskCleared(a, this.staleDays)
        const belowMA20 = k.ma20 > 0 && q.price > 0 && q.price < k.ma20
        const cardAlerts = this.alerts.filter((x) => x.code === item.code)
        let pnl = 0
        let pnlPct = 0
        if (pos && q.price > 0) {
          pnl = (q.price - pos.buyPrice) * pos.shares
          pnlPct = pos.buyPrice > 0 ? (q.price - pos.buyPrice) / pos.buyPrice * 100 : 0
        }
        const rawScoreRating = score != null ? (score >= 60 ? '可买入' : null) : null
        return {
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
          pnl,
          pnlPct,
          gateBlocked: rawScoreRating === '可买入' && rating === '观察',
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
      if (this.sector !== 'all') list = list.filter((c) => c.sector === this.sector)
      if (this.search) {
        const q = this.search.toLowerCase()
        list = list.filter((c) =>
          c.name.toLowerCase().includes(q)
          || c.code.toLowerCase().includes(q)
          || c.sector.toLowerCase().includes(q))
      }
      list.sort((a, b) => b.score - a.score)
      return list
    },
  },
  actions: {
    async refresh() {
      this.loading = true
      this.error = ''
      try {
        const [h, q, m, k, p, a, j, sf] = await Promise.all([
          api.health().catch(() => null),
          api.quotes(),
          api.market(),
          api.klines(),
          api.positions(),
          api.analyses(),
          api.journal().catch(() => ({ journal: [] })),
          api.sectorFlow().catch(() => null),
        ])
        this.health = h
        this.quotes = q.quotes || {}
        this.breadth = q.breadth || this.breadth
        this.marketBreadth = q.marketBreadth || this.marketBreadth
        this.overseas = q.overseas
        this.limitUpStats = q.limitUpStats || this.limitUpStats
        this.lastUpdate = q.lastUpdate
        this.indices = m.indices || {}
        this.klines = k.klines || {}
        this.positions = p.positions || {}
        this.analyses = a.analyses || {}
        if (a.staleDays) this.staleDays = a.staleDays
        this.journal = j.journal || []
        if (sf && Array.isArray(sf.list)) this.sectorFlow = sf
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
