import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 60000 })

export const api = {
  health: () => http.get('/health').then((r) => r.data),
  quotes: () => http.get('/quotes').then((r) => r.data),
  market: () => http.get('/market').then((r) => r.data),
  klines: () => http.get('/klines').then((r) => r.data),
  positions: () => http.get('/positions').then((r) => r.data),
  analyses: () => http.get('/analyses').then((r) => r.data),
  journal: () => http.get('/journal').then((r) => r.data),
  chat: (question, history = []) =>
    http.post('/jarvis/chat', { question, history }).then((r) => r.data),
  applyPatch: (patch, accept = true) =>
    http.post('/jarvis/patches/apply', { patch, accept }).then((r) => r.data),
  reindex: () => http.post('/jarvis/kb/reindex').then((r) => r.data),
}
