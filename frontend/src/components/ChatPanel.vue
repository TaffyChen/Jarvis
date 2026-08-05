<template>
  <aside class="chat-dock">
    <div class="chat-head">
      <div class="chat-head-title">
        <h3>Jarvis</h3>
        <span class="chat-head-sub">交易参谋 · RAG 先检索再答</span>
      </div>
      <div class="chat-head-actions">
        <button class="btn btn-sm" @click="chat.messages = []">清空</button>
        <button class="btn btn-sm" @click="$emit('close')">收起</button>
      </div>
    </div>

    <div class="chat-body" ref="bodyRef">
      <div v-if="!chat.messages.length && !chat.sending" class="chat-empty">
        <p class="chat-empty-lead">可以直接问持仓、纪律、单票判断。</p>
        <div class="chat-quick">
          <button
            v-for="q in quickPrompts"
            :key="q"
            type="button"
            class="chat-quick-btn"
            @click="sendQuick(q)"
          >{{ q }}</button>
        </div>
      </div>

      <div
        v-for="(m, i) in chat.messages"
        :key="i"
        :class="['msg-row', m.role, { system: m.system }]"
      >
        <div class="msg-avatar" aria-hidden="true">{{ m.role === 'user' ? '我' : 'J' }}</div>
        <div class="msg-main">
          <div class="msg-meta-line">
            <span class="msg-name">{{ m.role === 'user' ? '你' : 'Jarvis' }}</span>
          </div>

          <div
            v-if="m.role === 'assistant' && !m.system"
            class="msg-bubble assistant md-body"
            v-html="renderAssistantHtml(m.content)"
          />
          <div v-else class="msg-bubble" :class="m.role">{{ m.content }}</div>

          <!-- 工具链：紧凑芯片 -->
          <div v-if="m.toolTrace?.length" class="msg-chips">
            <span class="chip-label">工具</span>
            <span
              v-for="(t, j) in m.toolTrace"
              :key="'tt'+j"
              class="chip"
              :title="formatToolTitle(t)"
            >{{ shortTool(t.tool) }}</span>
          </div>

          <!-- 引用 / 沉淀：默认折叠 -->
          <details
            v-if="(m.sources?.length || m.memoriesUsed?.length) && m.role === 'assistant'"
            class="msg-refs"
          >
            <summary>
              依据
              <span v-if="m.sources?.length">· 知识 {{ Math.min(m.sources.length, 6) }}</span>
              <span v-if="m.memoriesUsed?.length">· 沉淀 {{ m.memoriesUsed.length }}</span>
            </summary>
            <ul v-if="m.memoriesUsed?.length" class="ref-list">
              <li v-for="(mem, j) in m.memoriesUsed.slice(0, 6)" :key="'mu'+j">
                沉淀 · {{ mem.title || mem.id }}
              </li>
            </ul>
            <ul v-if="m.sources?.length" class="ref-list">
              <li v-for="(s, j) in topSources(m.sources)" :key="'s'+j">
                {{ prettySource(s.source) }}
                <span v-if="s.score != null" class="ref-score">{{ Number(s.score).toFixed(2) }}</span>
              </li>
            </ul>
          </details>

          <div v-if="m.patch" class="patch-box">
            <div class="action-title">待确认操作</div>
            <div class="action-summary">{{ m.patch.summary || '（无摘要）' }}</div>
            <ul v-if="m.patch.patches?.length" class="patch-items">
              <li v-for="(p, pi) in m.patch.patches" :key="pi">
                {{ describePatchItem(p) }}
              </li>
            </ul>
            <div class="action-btns">
              <button class="btn btn-sm btn-primary" @click="onAccept(m.patch)">采纳并写入</button>
              <button class="btn btn-sm" @click="chat.rejectPatch()">忽略</button>
            </div>
          </div>

          <div v-if="m.memoryPatch" class="memory-box">
            <div class="action-title">对话沉淀</div>
            <div class="action-summary">{{ m.memoryPatch.summary || '（无摘要）' }}</div>
            <ul v-if="m.memoryPatch.memories?.length" class="memory-list">
              <li v-for="(mem, k) in m.memoryPatch.memories" :key="k">
                <span class="memory-kind">{{ mem.kind || 'insight' }}</span>
                {{ mem.title || mem.content }}
                <span v-if="mem.code" class="memory-code">{{ mem.code }}</span>
              </li>
            </ul>
            <div class="action-btns">
              <button class="btn btn-sm btn-primary" @click="onAcceptMemory(m)">确认记住</button>
              <button class="btn btn-sm" @click="chat.rejectMemory()">忽略</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="chat.sending" class="msg-row assistant">
        <div class="msg-avatar" aria-hidden="true">J</div>
        <div class="msg-main">
          <div class="msg-meta-line"><span class="msg-name">Jarvis</span></div>
          <div class="msg-bubble assistant typing">
            <span /><span /><span />
            正在检索与思考…
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input">
      <textarea
        v-model="draft"
        class="chat-textarea"
        placeholder="问持仓、单票、纪律；或「记住：…」。Enter 发送，Shift+Enter 换行"
        rows="3"
        @keydown.enter.exact.prevent="onSend"
      />
      <button class="btn btn-primary chat-send" :disabled="chat.sending || !draft.trim()" @click="onSend">
        {{ chat.sending ? '…' : '发送' }}
      </button>
    </div>
  </aside>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import { useDashboardStore } from '../stores/dashboard'
import { renderAssistantHtml } from '../utils/markdown'

defineEmits(['close'])
const chat = useChatStore()
const dash = useDashboardStore()
const draft = ref('')
const bodyRef = ref(null)

const quickPrompts = [
  '现在持仓有哪些？',
  '三环集团还能持有吗？',
  '现在五灯怎么看？',
  '记住：持仓不加仓，只做纪律执行',
]

function shortTool(name) {
  const map = {
    rag_retrieve: '检索',
    search_knowledge: '知识',
    search_memory: '沉淀',
    get_quote: '行情',
    get_score: '评分',
    get_analysis: '分析',
    get_positions: '持仓',
    get_market_overview: '大盘',
    get_journal: '日记',
  }
  return map[name] || name
}

function formatToolTitle(t) {
  const args = t?.args && Object.keys(t.args).length ? JSON.stringify(t.args) : ''
  return args ? `${t.tool} ${args}` : t.tool
}

function prettySource(src) {
  if (!src) return ''
  return String(src).replace(/^analyses\//, '').replace(/\.md$/, '')
}

function topSources(sources) {
  return [...(sources || [])]
    .sort((a, b) => (b.score || 0) - (a.score || 0))
    .slice(0, 6)
}

function describePatchItem(p) {
  if (!p) return ''
  const code = p.code || p.payload?.code || ''
  const name = p.payload?.name || p.name || ''
  if (p.target === 'codes') return `添加标的 ${code || '（缺代码）'}`
  if (p.target === 'positions') {
    if (['remove', 'delete', 'clear'].includes(p.action)) {
      return `删除持仓 ${name || code || '（缺代码）'}`
    }
    const buy = p.payload?.buyPrice ?? p.payload?.buy_price
    const shares = p.payload?.shares
    return `写入持仓 ${code || name} 成本${buy ?? '?'} × ${shares ?? '?'}`
  }
  if (p.target === 'analyses') return `更新分析 ${code} · ${p.action || ''}`
  if (p.target === 'journal') return '追加日记'
  if (p.target === 'rules') return '策略规则提案'
  return `${p.target || '操作'} ${code}`.trim()
}

async function scrollBottom() {
  await nextTick()
  if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
}

async function onSend() {
  const t = draft.value
  draft.value = ''
  await chat.send(t)
  await scrollBottom()
}

async function sendQuick(q) {
  draft.value = ''
  await chat.send(q)
  await scrollBottom()
}

async function onAccept(patch) {
  await chat.acceptPatch(patch)
  await dash.refresh()
  await scrollBottom()
}

async function onAcceptMemory(m) {
  await chat.acceptMemory(m.memoryPatch, m.sourceQuestion || '')
  await dash.refresh()
  await scrollBottom()
}

watch(
  () => [chat.messages.length, chat.sending],
  () => scrollBottom(),
)
</script>
