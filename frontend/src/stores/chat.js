import { defineStore } from 'pinia'
import { api } from '../api'

function groupSessions(sessions) {
  const groups = [
    { label: '今天', items: [] },
    { label: '更早', items: [] },
  ]
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  for (const s of sessions || []) {
    const t = s.updatedAt ? new Date(s.updatedAt).getTime() : 0
    if (t >= start.getTime()) groups[0].items.push(s)
    else groups[1].items.push(s)
  }
  return groups.filter((g) => g.items.length)
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    sending: false,
    lastPatch: null,
    lastMemoryPatch: null,
    open: true,
    sessionId: null,
    sessions: [],
    sessionsLoading: false,
    sidebarOpen: true,
  }),
  getters: {
    sessionGroups(state) {
      return groupSessions(state.sessions)
    },
  },
  actions: {
    async refreshSessions() {
      this.sessionsLoading = true
      try {
        const r = await api.chatSessions()
        this.sessions = r.sessions || []
      } catch {
        this.sessions = []
      } finally {
        this.sessionsLoading = false
      }
    },
    async newSession() {
      try {
        const r = await api.createChatSession('')
        this.sessionId = r.session?.id ?? null
      } catch {
        this.sessionId = null
      }
      this.messages = []
      this.lastPatch = null
      this.lastMemoryPatch = null
      await this.refreshSessions()
    },
    async openSession(id) {
      if (!id || this.sending) return
      const r = await api.chatSession(id)
      this.sessionId = r.session?.id ?? id
      this.messages = r.messages || []
      this.lastPatch = null
      this.lastMemoryPatch = null
    },
    async send(text) {
      const q = (text || '').trim()
      if (!q || this.sending) return
      this.sending = true
      this.messages.push({ role: 'user', content: q })
      try {
        const history = this.messages
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .slice(-8)
          .map((m) => ({ role: m.role, content: m.content }))
        const res = await api.chat(q, history.slice(0, -1), this.sessionId)
        if (res.sessionId != null) this.sessionId = res.sessionId
        this.messages.push({
          role: 'assistant',
          content: res.answer || '',
          sources: res.sources || [],
          patch: res.patch || null,
          memoryPatch: res.memoryPatch || null,
          memoriesUsed: res.memoriesUsed || [],
          toolTrace: res.toolTrace || [],
          retrieveQueries: res.retrieveQueries || [],
          orchestrator: res.orchestrator || null,
          sourceQuestion: q,
        })
        this.lastPatch = res.patch || null
        this.lastMemoryPatch = res.memoryPatch || null
        await this.refreshSessions()
      } catch (e) {
        this.messages.push({
          role: 'assistant',
          content: '请求失败：' + (e.message || e),
        })
      } finally {
        this.sending = false
      }
    },
    async acceptPatch(patch) {
      if (!patch) return
      await api.applyPatch(patch, true)
      this.messages.push({
        role: 'assistant',
        system: true,
        content: '已采纳并写入本地（标的/持仓/分析等）。可在看板刷新后查看。',
      })
      this.lastPatch = null
    },
    rejectPatch() {
      this.lastPatch = null
      this.messages.push({ role: 'assistant', system: true, content: '已忽略本次策略补丁。' })
    },
    async acceptMemory(patch, sourceQuestion = '') {
      if (!patch) return
      const res = await api.applyMemory(patch, true, sourceQuestion)
      const n = res?.applied ?? 0
      this.messages.push({
        role: 'assistant',
        system: true,
        content: n
          ? `已确认沉淀 ${n} 条认知卡片，下次回答会优先参考。`
          : '沉淀未写入（内容为空）。',
      })
      this.lastMemoryPatch = null
    },
    rejectMemory() {
      this.lastMemoryPatch = null
      this.messages.push({ role: 'assistant', system: true, content: '已忽略本次对话沉淀。' })
    },
  },
})
