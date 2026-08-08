import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 120000 })
const TOKEN_KEY = 'jarvis-auth-token'

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers['x-jarvis-token'] = token
  return config
})

http.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('jarvis-auth-v1')
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('jarvis-account')
      localStorage.removeItem('jarvis-display-name')
    }
    return Promise.reject(err)
  },
)

export const api = {
  login: (account, password) =>
    http.post('/auth/login', { account, password }).then((r) => r.data),
  me: () => http.get('/auth/me').then((r) => r.data),
  logout: () => http.post('/auth/logout').then((r) => r.data),
  health: () => http.get('/health').then((r) => r.data),
  quotes: () => http.get('/quotes').then((r) => r.data),
  market: () => http.get('/market').then((r) => r.data),
  klines: () => http.get('/klines').then((r) => r.data),
  positions: () => http.get('/positions').then((r) => r.data),
  savePositions: (positions) => http.post('/positions', { positions }).then((r) => r.data),
  analyses: () => http.get('/analyses').then((r) => r.data),
  upsertAnalysis: (body) => http.post('/analyses', body).then((r) => r.data),
  journal: (params = {}) => http.get('/journal', { params }).then((r) => r.data),
  addJournal: (entry) => http.post('/journal', { entry }).then((r) => r.data),
  searchCodes: (q) => http.get('/codes/search', { params: { q, limit: 8 } }).then((r) => r.data),
  addCodes: (codes) => http.post('/codes/add', { codes }).then((r) => r.data),
  removeCodes: (codes) => http.post('/codes/remove', { codes }).then((r) => r.data),
  screen: () => http.get('/screen').then((r) => r.data),
  screenStrategyDoc: (strategyId) =>
    http.get('/screen/strategy-doc', { params: { strategyId } }).then((r) => r.data),
  screenAnalyze: (strategyId, code, row = null) =>
    http.post('/screen/analyze', { strategyId, code, row }).then((r) => r.data),
  auction: () => http.get('/auction').then((r) => r.data),
  sectorFlow: () => http.get('/sector-flow').then((r) => r.data),
  chat: (question, history = [], sessionId = null) =>
    http.post('/jarvis/chat', { question, history, sessionId }).then((r) => r.data),
  chatSessions: () => http.get('/jarvis/chat/sessions').then((r) => r.data),
  createChatSession: (title = '') =>
    http.post('/jarvis/chat/sessions', { title }).then((r) => r.data),
  chatSession: (id) => http.get(`/jarvis/chat/sessions/${id}`).then((r) => r.data),
  applyPatch: (patch, accept = true) =>
    http.post('/jarvis/patches/apply', { patch, accept }).then((r) => r.data),
  applyMemory: (patch, accept = true, sourceQuestion = '') =>
    http
      .post('/jarvis/memories/apply', { patch, accept, sourceQuestion })
      .then((r) => r.data),
  memories: () => http.get('/jarvis/memories').then((r) => r.data),
  kbStatus: () => http.get('/jarvis/kb').then((r) => r.data),
  kbDocument: (path) => http.get('/jarvis/kb/document', { params: { path } }).then((r) => r.data),
  saveKbDocument: (path, content, create = false) =>
    http.put('/jarvis/kb/document', { path, content, create }).then((r) => r.data),
  uploadKbDocument: (file, overwrite = false) => {
    const body = new FormData()
    body.append('file', file)
    body.append('overwrite', overwrite ? 'true' : 'false')
    return http.post('/jarvis/kb/upload', body).then((r) => r.data)
  },
  deleteKbDocument: (path) =>
    http.delete('/jarvis/kb/document', { params: { path } }).then((r) => r.data),
  previewKb: (body) => http.post('/jarvis/kb/preview', body).then((r) => r.data),
  searchKb: (query, top_k = 5) =>
    http.post('/jarvis/kb/search', { query, top_k }).then((r) => r.data),
  reindex: () => http.post('/jarvis/kb/reindex').then((r) => r.data),
  reviewSnapshot: () => http.get('/jarvis/review/snapshot').then((r) => r.data),
  reviewDays: () => http.get('/jarvis/review/days').then((r) => r.data),
  reviewDay: (date) => http.get(`/jarvis/review/days/${date}`).then((r) => r.data),
  reviewVersion: (id) => http.get(`/jarvis/review/versions/${id}`).then((r) => r.data),
  reviewGenerate: (body = {}) => http.post('/jarvis/review/generate', body).then((r) => r.data),
  reviewComment: (id, text) =>
    http.post(`/jarvis/review/versions/${id}/comments`, { text }).then((r) => r.data),
  reviewMarkFinal: (id) => http.post(`/jarvis/review/versions/${id}/final`).then((r) => r.data),
}
