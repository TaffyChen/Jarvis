import { defineStore } from 'pinia'
import { api } from '../api'

const AUTH_KEY = 'jarvis-auth-v1'
const TOKEN_KEY = 'jarvis-auth-token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    isAuthed: localStorage.getItem(AUTH_KEY) === '1' && !!localStorage.getItem(TOKEN_KEY),
    account: localStorage.getItem('jarvis-account') || '',
    displayName: localStorage.getItem('jarvis-display-name') || '',
    roles: [],
    permissions: [],
  }),
  getters: {
    roleLabel(state) {
      const names = (state.roles || []).map((r) => r.name || r.code).filter(Boolean)
      return names.join(' / ')
    },
    isAdmin(state) {
      return (state.roles || []).some((r) => r.code === 'admin')
        || (state.permissions || []).includes('user.manage')
    },
    can(state) {
      return (code) => {
        if ((state.roles || []).some((r) => r.code === 'admin')) return true
        return (state.permissions || []).includes(code)
      }
    },
  },
  actions: {
    applyUser(payload = {}, accountFallback = '') {
      this.account = payload.account || accountFallback || ''
      this.displayName = payload.displayName || this.account
      this.roles = payload.roles || []
      this.permissions = payload.permissions || []
      localStorage.setItem('jarvis-account', this.account)
      localStorage.setItem('jarvis-display-name', this.displayName)
    },
    async login(account, password) {
      const r = await api.login(account, password)
      if (r?.ok && r?.token) {
        this.isAuthed = true
        this.applyUser(r, account)
        localStorage.setItem(AUTH_KEY, '1')
        localStorage.setItem(TOKEN_KEY, r.token)
        return { ok: true }
      }
      return { ok: false, error: r?.error || '登录失败' }
    },
    async restore() {
      const token = localStorage.getItem(TOKEN_KEY)
      if (!token) {
        this.logoutLocal()
        return { ok: false }
      }
      try {
        const me = await api.me()
        if (me?.ok && me?.authed) {
          this.isAuthed = true
          this.applyUser(me, localStorage.getItem('jarvis-account') || '')
          localStorage.setItem(AUTH_KEY, '1')
          return { ok: true }
        }
      } catch { /* ignore */ }
      this.logoutLocal()
      return { ok: false }
    },
    logoutLocal() {
      this.isAuthed = false
      this.account = ''
      this.displayName = ''
      this.roles = []
      this.permissions = []
      localStorage.removeItem(AUTH_KEY)
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('jarvis-account')
      localStorage.removeItem('jarvis-display-name')
    },
    async logout() {
      try {
        await api.logout()
      } catch { /* ignore */ }
      this.logoutLocal()
    },
  },
})
