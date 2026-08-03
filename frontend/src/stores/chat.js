import { defineStore } from 'pinia'
import { api } from '../api'

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    sending: false,
    lastPatch: null,
    open: true,
  }),
  actions: {
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
        const res = await api.chat(q, history.slice(0, -1))
        this.messages.push({
          role: 'assistant',
          content: res.answer || '',
          sources: res.sources || [],
          patch: res.patch || null,
        })
        this.lastPatch = res.patch || null
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
        content: '已采纳策略补丁并写入本地数据。',
      })
      this.lastPatch = null
    },
    rejectPatch() {
      this.lastPatch = null
      this.messages.push({ role: 'assistant', content: '已忽略本次策略补丁。' })
    },
  },
})
