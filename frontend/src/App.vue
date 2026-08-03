<template>
  <div class="app">
    <main class="main">
      <div class="topbar">
        <div>
          <div class="brand">Jarvis · 交易参谋</div>
          <div class="sub">
            {{ dash.lastUpdate ? ('行情更新 ' + formatTime(dash.lastUpdate)) : '等待行情…' }}
            · LLM {{ dash.health?.llmConfigured ? '已配置' : '未配置 Key' }}
          </div>
        </div>
        <div class="actions">
          <button class="btn" @click="dash.refresh()" :disabled="dash.loading">刷新</button>
          <button class="btn" @click="onReindex">重建知识库</button>
          <button class="btn primary" @click="chat.open = !chat.open">
            {{ chat.open ? '收起对话' : '打开对话' }}
          </button>
        </div>
      </div>

      <div v-if="dash.error" class="error">{{ dash.error }}</div>

      <div class="market-row">
        <div v-for="(name, code) in indexNames" :key="code" class="chip">
          {{ name }}
          <b>{{ fmt(dash.indices[code]?.price) }}</b>
          <span :class="chgClass(dash.indices[code]?.changePct)">
            {{ fmtPct(dash.indices[code]?.changePct) }}
          </span>
        </div>
        <div class="chip">
          全市场
          <span class="up">↑{{ dash.marketBreadth.up || 0 }}</span>
          /
          <span class="down">↓{{ dash.marketBreadth.down || 0 }}</span>
        </div>
        <div class="chip" v-if="dash.overseas">
          标普 {{ fmtPct(dash.overseas.changePct) }}
        </div>
      </div>

      <div class="grid" v-if="dash.cards.length">
        <div class="card" v-for="c in dash.cards" :key="c.code">
          <div class="card-head">
            <div>
              <span class="name">{{ c.name }}</span>
              <span class="code">{{ c.code }}</span>
              <span v-if="c.held" class="badge hold">持仓</span>
              <span
                class="badge"
                :class="c.riskOk === true ? 'ok' : c.riskOk === false ? 'bad' : 'unknown'"
              >
                {{ c.riskOk === true ? '利空已复核' : c.riskOk === false ? '利空未过' : '待复核' }}
              </span>
            </div>
            <div :class="['price', chgClass(c.changePct)]">{{ fmt(c.price) }}</div>
          </div>
          <div :class="chgClass(c.changePct)">{{ fmtPct(c.changePct) }}</div>
          <div class="meta">
            <div><span>PE</span> {{ fmt(c.pe, 1) }}</div>
            <div><span>委比</span> {{ fmt(c.weibi, 1) }}%</div>
            <div><span>MA20</span> {{ fmt(c.ma20) }}</div>
            <div><span>20日</span> {{ fmtPct(c.change20d) }}</div>
          </div>
          <div class="reason" v-if="c.reason">📋 {{ c.reason }}</div>
          <div class="reason" v-if="c.held">
            成本 {{ c.buyPrice }} · {{ c.shares }} 股
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无标的数据。请启动后端后点刷新。</div>
    </main>

    <aside class="chat-dock" v-show="chat.open">
      <div class="chat-head">
        <h2>Jarvis 对话</h2>
        <button class="btn" @click="chat.messages = []">清空</button>
      </div>
      <div class="chat-body" ref="bodyRef">
        <div v-if="!chat.messages.length" class="empty">
          问策略、利空、仓位纪律。Jarvis 会检索本地知识库后回答；
          若建议改策略，会给出补丁供你确认。
        </div>
        <div
          v-for="(m, i) in chat.messages"
          :key="i"
          :class="['msg', m.role]"
        >
          {{ m.content }}
          <div v-if="m.sources?.length" class="sources">
            引用：
            <span v-for="(s, j) in m.sources" :key="j">
              {{ s.source }}({{ s.score }}){{ j < m.sources.length - 1 ? ' · ' : '' }}
            </span>
          </div>
          <div v-if="m.patch" class="patch-box">
            <div>策略补丁提案：{{ m.patch.summary || '（无摘要）' }}</div>
            <div style="margin-top:8px;display:flex;gap:8px">
              <button class="btn primary" @click="onAccept(m.patch)">采纳</button>
              <button class="btn" @click="chat.rejectPatch()">忽略</button>
            </div>
          </div>
        </div>
      </div>
      <div class="chat-input">
        <textarea
          v-model="draft"
          placeholder="例如：现在五灯怎么看？三环集团还能持有吗？"
          @keydown.enter.exact.prevent="onSend"
        />
        <button class="btn primary" :disabled="chat.sending" @click="onSend">
          {{ chat.sending ? '…' : '发送' }}
        </button>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, nextTick, watch } from 'vue'
import { useDashboardStore } from './stores/dashboard'
import { useChatStore } from './stores/chat'
import { api } from './api'

const dash = useDashboardStore()
const chat = useChatStore()
const draft = ref('')
const bodyRef = ref(null)
let timer = null

const indexNames = {
  sh000001: '上证',
  sz399001: '深成',
  sz399006: '创业',
  sh000688: '科创50',
  sh000300: '沪深300',
}

function fmt(v, d = 2) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(d)
}
function fmtPct(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  return (n > 0 ? '+' : '') + n.toFixed(2) + '%'
}
function chgClass(v) {
  const n = Number(v)
  if (!n) return ''
  return n > 0 ? 'up' : 'down'
}
function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString('zh-CN') } catch { return iso }
}

async function onSend() {
  const t = draft.value
  draft.value = ''
  await chat.send(t)
  await nextTick()
  if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
}

async function onAccept(patch) {
  await chat.acceptPatch(patch)
  await dash.refresh()
}

async function onReindex() {
  try {
    const r = await api.reindex()
    alert('知识库已重建：' + r.chunks + ' 个片段')
  } catch (e) {
    alert('重建失败：' + (e.message || e))
  }
}

watch(
  () => chat.messages.length,
  async () => {
    await nextTick()
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  }
)

onMounted(async () => {
  await dash.refresh()
  timer = setInterval(() => dash.refresh(), 10000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>
