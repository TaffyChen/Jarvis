import { defineStore } from 'pinia'
import { api } from '../api'

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    quotes: {},
    indices: {},
    klines: {},
    positions: {},
    analyses: {},
    breadth: { up: 0, down: 0, flat: 0, total: 0 },
    marketBreadth: { up: 0, down: 0, flat: 0, total: 0, source: '' },
    overseas: null,
    lastUpdate: null,
    health: null,
    loading: false,
    error: '',
  }),
  getters: {
    cards(state) {
      const list = []
      const codes = new Set([
        ...Object.keys(state.quotes),
        ...Object.keys(state.analyses),
        ...Object.keys(state.positions),
      ])
      for (const code of codes) {
        const q = state.quotes[code] || {}
        const a = state.analyses[code] || {}
        const k = state.klines[code] || {}
        const pos = state.positions[code]
        list.push({
          code,
          name: q.name || a.name || code,
          price: q.price || 0,
          changePct: q.changePct || 0,
          pe: q.peTTM || q.pe || 0,
          weibi: q.weibi || 0,
          ma20: k.ma20 || 0,
          change20d: k.change20d || 0,
          reason: a.reason || '',
          notes: a.notes || '',
          riskOk: a.riskOk,
          reviewedAt: a.reviewedAt,
          analysis: a.analysis || [],
          held: !!pos,
          buyPrice: pos?.buyPrice,
          shares: pos?.shares,
        })
      }
      return list.sort((a, b) => Math.abs(b.changePct) - Math.abs(a.changePct))
    },
  },
  actions: {
    async refresh() {
      this.loading = true
      this.error = ''
      try {
        const [h, q, m, k, p, a] = await Promise.all([
          api.health().catch(() => null),
          api.quotes(),
          api.market(),
          api.klines(),
          api.positions(),
          api.analyses(),
        ])
        this.health = h
        this.quotes = q.quotes || {}
        this.breadth = q.breadth || this.breadth
        this.marketBreadth = q.marketBreadth || this.marketBreadth
        this.overseas = q.overseas
        this.lastUpdate = q.lastUpdate
        this.indices = m.indices || {}
        this.klines = k.klines || {}
        this.positions = p.positions || {}
        this.analyses = a.analyses || {}
      } catch (e) {
        this.error = e.message || '加载失败，请确认后端已启动 :1690'
      } finally {
        this.loading = false
      }
    },
  },
})
