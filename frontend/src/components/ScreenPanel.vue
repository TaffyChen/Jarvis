<template>
  <div class="panel-card screen-panel">
    <div class="panel-head">
      <div>
        <h3>策略选股</h3>
        <div class="muted" v-if="meta">
          宇宙 {{ meta.universe }} · 扫描 {{ meta.scanned }} · {{ formatTime(meta.lastUpdate) }}
        </div>
        <div v-if="meta?.discipline?.hint" class="discipline-banner">{{ meta.discipline.hint }} · {{ meta.discipline.text }}</div>
        <div v-else-if="meta?.discipline?.text" class="muted" style="font-size:12px;margin-top:4px">
          纪律：{{ meta.discipline.text }}
        </div>
      </div>
      <button class="btn btn-primary" :disabled="loading" @click="$emit('refresh')">
        {{ loading ? '扫描中…' : '扫描刷新' }}
      </button>
    </div>

    <div class="strategy-tabs" role="tablist">
      <button
        v-for="s in strategies"
        :key="s.id"
        type="button"
        role="tab"
        :class="['strategy-tab', { active: activeId === s.id }]"
        @click="selectStrategy(s.id)"
      >
        <b>{{ s.name }}</b>
        <em>{{ s.badge }}</em>
        <span class="muted">{{ s.shown ?? 0 }}/{{ s.topN }}</span>
      </button>
    </div>

    <section v-if="active" class="screen-block">
      <div class="block-head">
        <div>
          <h4>
            {{ active.name }} · TOP{{ active.topN }}
            <span class="badge-core">{{ active.badge }}</span>
          </h4>
          <div class="muted block-sub">
            <template v-if="active.stage">阶段 {{ active.stage }} · </template>
            达标 {{ active.candidates ?? active.rows?.length ?? 0 }} · 展示 {{ active.shown ?? 0 }}
            <span v-if="active.note"> · {{ active.note }}</span>
          </div>
          <div class="muted block-sub">{{ active.blurb }}</div>
        </div>
        <button type="button" class="btn btn-sm btn-ghost" @click="toggleDoc">
          {{ docOpen ? '收起策略' : '查看策略' }}
        </button>
      </div>

      <div v-if="docOpen" class="strategy-doc">
        <div v-if="docLoading" class="muted">加载策略说明…</div>
        <div v-else-if="docError" class="muted">{{ docError }}</div>
        <div v-else class="doc-body" v-html="renderStrategyMd(docText)"></div>
      </div>

      <div style="overflow:auto">
        <table class="screen-table">
          <thead>
            <tr>
              <th>#</th>
              <th>名称</th>
              <th>代码</th>
              <th>现价</th>
              <th>涨跌%</th>
              <th>20日%</th>
              <th>MA20</th>
              <th>得分</th>
              <th class="col-why">入选理由</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!(active.rows || []).length">
              <td colspan="10" style="text-align:center;color:var(--muted);padding:20px">
                {{ loading ? '扫描中…' : '暂无达标票，点「扫描刷新」或换策略看看' }}
              </td>
            </tr>
            <tr
              v-for="(row, i) in (active.rows || [])"
              :key="active.id + '-' + row.code"
              :class="{ dimmed: row.flags?.buyDiscouraged }"
            >
              <td>
                <span :class="['screen-rank', i === 0 ? 'top1' : i === 1 ? 'top2' : i === 2 ? 'top3' : 'other']">
                  {{ i + 1 }}
                </span>
              </td>
              <td>
                {{ row.name }}
                <span v-if="row.flags?.inPosition" class="flag-pill">持仓</span>
              </td>
              <td>{{ row.code?.replace(/^(sh|sz)/, '') }}</td>
              <td>{{ fmt(row.price) }}</td>
              <td :class="chgClass(row.changePct)">{{ fmtPct(row.changePct) }}</td>
              <td :class="chgClass(row.change20d)">{{ fmtPct(row.change20d) }}</td>
              <td :class="row.aboveMA20 === true ? 'up' : row.aboveMA20 === false ? 'down' : ''">
                {{ row.aboveMA20 === true ? '上方' : row.aboveMA20 === false ? '下方' : '--' }}
              </td>
              <td><b>{{ scoreOf(row) }}</b></td>
              <td class="col-why">
                <div class="why-line" :title="(row.why || []).join(' · ')">
                  <span
                    v-for="(w, j) in (row.why || row.signals || []).slice(0, 3)"
                    :key="j"
                    :class="['sig-pill', warnSig(w) ? 'warn' : '']"
                  >{{ w }}</span>
                </div>
              </td>
              <td class="row-actions">
                <button
                  class="btn btn-sm btn-ghost"
                  :disabled="analyzeKey === rowKey(row)"
                  @click="analyze(row)"
                >{{ analyzeKey === rowKey(row) ? '…' : '深析' }}</button>
                <button
                  class="btn btn-sm btn-primary"
                  :title="row.flags?.buyDiscouraged ? '纪律提示：今日不宜新开，加入仅作观察' : '加入自选后仍须利空复核'"
                  @click="$emit('add', row)"
                >加入</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="analyzeMd" class="analyze-box">
        <div class="analyze-head">
          <b>深析 · {{ analyzeTitle }}</b>
          <button type="button" class="btn btn-sm btn-ghost" @click="analyzeMd = ''">关闭</button>
        </div>
        <div class="analyze-body" v-html="renderMd(analyzeMd)"></div>
        <div class="muted" style="font-size:11px;margin-top:6px">{{ analyzeModeHint }}</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  trendRows: { type: Array, default: () => [] },
  meta: { type: Object, default: null },
  loading: Boolean,
})
defineEmits(['refresh', 'add'])

const activeId = ref('trend')
const docOpen = ref(false)
const docText = ref('')
const docLoading = ref(false)
const docError = ref('')
const docCache = ref({})
const analyzeKey = ref('')
const analyzeMd = ref('')
const analyzeTitle = ref('')
const analyzeMode = ref('')

const fallbackStrategies = computed(() => ([
  {
    id: 'trend',
    name: '趋势波段',
    badge: 'L1 观察',
    doc: '趋势波段策略.md',
    topN: 5,
    scoreKey: 'trendScore',
    blurb: '站上 MA20 + 趋势结构排序',
    rows: props.trendRows || [],
    shown: (props.trendRows || []).length,
    candidates: props.meta?.trendMeta?.candidates,
    stage: props.meta?.trendMeta?.stage,
    note: props.meta?.trendMeta?.note,
  },
  {
    id: 'quality',
    name: '综合质量',
    badge: '多因子',
    doc: '盘后选股与竞价异动.md',
    topN: 10,
    scoreKey: 'score',
    blurb: '估值 + 趋势 + 量能',
    rows: props.rows || [],
    shown: (props.rows || []).length,
  },
]))

const strategies = computed(() => {
  const list = props.meta?.strategies
  if (Array.isArray(list) && list.length) return list
  return fallbackStrategies.value
})

const active = computed(() => strategies.value.find((s) => s.id === activeId.value) || strategies.value[0] || null)

watch(strategies, (list) => {
  if (!list?.length) return
  if (!list.some((s) => s.id === activeId.value)) activeId.value = list[0].id
}, { immediate: true })

function selectStrategy(id) {
  activeId.value = id
  docOpen.value = false
  analyzeMd.value = ''
}

function scoreOf(row) {
  const key = active.value?.scoreKey || 'score'
  const v = row?.[key]
  return v != null ? v : (row?.score ?? '--')
}

function rowKey(row) {
  return `${activeId.value}:${row?.code || ''}`
}

async function toggleDoc() {
  docOpen.value = !docOpen.value
  if (!docOpen.value || !active.value?.doc) return
  const path = active.value.doc
  if (docCache.value[path]) {
    docText.value = docCache.value[path]
    return
  }
  docLoading.value = true
  docError.value = ''
  try {
    const r = await api.screenStrategyDoc(active.value.id)
    const text = r?.content || ''
    if (!r?.ok || !text) throw new Error(r?.error || 'empty')
    docCache.value[path] = text
    docText.value = text
  } catch {
    docError.value = `无法加载 ${path}`
    docText.value = ''
  } finally {
    docLoading.value = false
  }
}

async function analyze(row) {
  if (!row?.code || !active.value) return
  analyzeKey.value = rowKey(row)
  analyzeMd.value = ''
  analyzeTitle.value = `${row.name || row.code} · ${active.value.name}`
  try {
    const r = await api.screenAnalyze(active.value.id, row.code, row)
    analyzeMd.value = r?.markdown || '（无内容）'
    analyzeMode.value = r?.mode || ''
  } catch (e) {
    analyzeMd.value = `深析失败：${e?.message || e}`
    analyzeMode.value = 'error'
  } finally {
    analyzeKey.value = ''
  }
}

const analyzeModeHint = computed(() => {
  if (analyzeMode.value === 'llm') return '由大模型按策略条文与规则理由生成 · 非买卖指令'
  if (analyzeMode.value === 'rules') return '未配置 LLM，仅规则摘要'
  return ''
})

function renderMd(md) {
  return renderStrategyMd(md, { compact: true })
}

/** 策略原文轻量渲染：标题 / 表 / 列表 / 加粗；先转义防 XSS */
function renderStrategyMd(md, { compact = false } = {}) {
  const esc = String(md || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const lines = esc.split('\n')
  const out = []
  let i = 0
  let inCode = false
  let codeBuf = []

  const flushCode = () => {
    if (!codeBuf.length) return
    out.push(`<pre class="md-code">${codeBuf.join('\n')}</pre>`)
    codeBuf = []
  }

  while (i < lines.length) {
    const line = lines[i]
    if (line.trim().startsWith('```')) {
      if (inCode) {
        flushCode()
        inCode = false
      } else {
        inCode = true
      }
      i += 1
      continue
    }
    if (inCode) {
      codeBuf.push(line)
      i += 1
      continue
    }

    // GFM table: header + separator + rows
    if (
      line.includes('|')
      && i + 1 < lines.length
      && /^\s*\|?[\s:-]+\|/.test(lines[i + 1])
    ) {
      const rows = []
      while (i < lines.length && lines[i].includes('|')) {
        const raw = lines[i].trim()
        if (/^\|?[\s:-]+\|/.test(raw)) {
          i += 1
          continue
        }
        const cells = raw
          .replace(/^\|/, '')
          .replace(/\|$/, '')
          .split('|')
          .map((c) => inlineMd(c.trim()))
        rows.push(cells)
        i += 1
      }
      if (rows.length) {
        const [head, ...body] = rows
        out.push('<table class="md-table"><thead><tr>')
        head.forEach((c) => out.push(`<th>${c}</th>`))
        out.push('</tr></thead><tbody>')
        body.forEach((r) => {
          out.push('<tr>')
          r.forEach((c) => out.push(`<td>${c}</td>`))
          out.push('</tr>')
        })
        out.push('</tbody></table>')
      }
      continue
    }

    if (/^### /.test(line)) {
      out.push(`<h4>${inlineMd(line.slice(4))}</h4>`)
    } else if (/^## /.test(line)) {
      out.push(`<h3>${inlineMd(line.slice(3))}</h3>`)
    } else if (/^# /.test(line)) {
      out.push(compact ? `<h4>${inlineMd(line.slice(2))}</h4>` : `<h2>${inlineMd(line.slice(2))}</h2>`)
    } else if (/^[-*] /.test(line)) {
      out.push(`<div class="md-li">• ${inlineMd(line.slice(2))}</div>`)
    } else if (/^> /.test(line)) {
      out.push(`<blockquote>${inlineMd(line.slice(2))}</blockquote>`)
    } else if (!line.trim()) {
      out.push('<div class="md-gap"></div>')
    } else {
      out.push(`<p>${inlineMd(line)}</p>`)
    }
    i += 1
  }
  if (inCode) flushCode()
  return out.join('')
}

function inlineMd(s) {
  return String(s || '')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

function warnSig(s) {
  return /不宜新开|破20|放量滞|放量下跌|破开盘|涨幅偏大|涨幅已大|远离20|慎追|纪律/.test(String(s || ''))
}
function fmt(v, d = 2) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(d)
}
function fmtPct(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}
function chgClass(v) {
  const n = Number(v)
  if (!n) return ''
  return n > 0 ? 'up' : 'down'
}
function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString('zh-CN') } catch { return '' }
}
</script>

<style scoped>
.strategy-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0 4px;
}
.strategy-tab {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-width: 120px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--card-bg);
  color: inherit;
  cursor: pointer;
  text-align: left;
}
.strategy-tab:hover { border-color: rgba(88, 166, 255, 0.45); }
.strategy-tab.active {
  border-color: var(--blue);
  background: var(--blue-bg);
}
.strategy-tab b { font-size: 13px; color: var(--bright); }
.strategy-tab em {
  font-style: normal;
  font-size: 10px;
  color: var(--blue);
}
.strategy-tab span { font-size: 11px; }

.screen-block { margin-top: 10px; }
.block-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}
.block-head h4 {
  margin: 0 0 4px;
  font-size: 14px;
  color: var(--bright);
  display: flex;
  align-items: center;
  gap: 8px;
}
.block-sub { font-size: 12px; margin-top: 2px; }
.badge-core {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid rgba(88, 166, 255, 0.35);
  color: var(--blue);
  background: var(--blue-bg);
}
.discipline-banner {
  margin-top: 6px;
  font-size: 12px;
  color: var(--orange);
}
.flag-pill {
  margin-left: 4px;
  font-size: 10px;
  padding: 0 5px;
  border-radius: 4px;
  background: var(--teal-bg, rgba(45, 212, 191, 0.15));
  color: var(--teal, #2dd4bf);
}
.sig-pill {
  display: inline-block;
  margin: 1px 3px 1px 0;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  background: rgba(139, 148, 158, 0.15);
  color: var(--muted);
}
.sig-pill.warn { color: var(--orange); background: var(--orange-bg); }
.col-why { min-width: 180px; max-width: 280px; }
.why-line {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}
.row-actions {
  white-space: nowrap;
  display: flex;
  gap: 4px;
}
.dimmed { opacity: 0.72; }

.strategy-doc {
  margin: 0 0 10px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--hover-soft, rgba(139, 148, 158, 0.06));
  max-height: min(42vh, 420px);
  overflow: auto;
}
.doc-body {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text);
}
.doc-body :deep(h2) {
  margin: 0 0 10px;
  font-size: 15px;
  color: var(--bright);
  font-weight: 650;
}
.doc-body :deep(h3) {
  margin: 14px 0 6px;
  font-size: 13px;
  color: var(--bright);
  font-weight: 600;
}
.doc-body :deep(h4) {
  margin: 10px 0 4px;
  font-size: 12.5px;
  color: var(--bright);
}
.doc-body :deep(p) {
  margin: 0 0 6px;
}
.doc-body :deep(.md-li) {
  margin: 2px 0 2px 2px;
  color: var(--text);
}
.doc-body :deep(.md-gap) {
  height: 6px;
}
.doc-body :deep(blockquote) {
  margin: 6px 0;
  padding: 6px 10px;
  border-left: 3px solid rgba(88, 166, 255, 0.45);
  background: var(--blue-bg);
  color: var(--muted);
  border-radius: 0 var(--radius-sm, 4px) var(--radius-sm, 4px) 0;
}
.doc-body :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  padding: 0 4px;
  border-radius: 3px;
  background: rgba(139, 148, 158, 0.15);
}
.doc-body :deep(.md-code) {
  margin: 8px 0;
  padding: 8px 10px;
  overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  line-height: 1.45;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: rgba(0, 0, 0, 0.2);
  color: var(--muted);
  white-space: pre;
}
.doc-body :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0 10px;
  font-size: 12px;
}
.doc-body :deep(.md-table th),
.doc-body :deep(.md-table td) {
  border: 1px solid var(--border);
  padding: 5px 8px;
  text-align: left;
  vertical-align: top;
}
.doc-body :deep(.md-table th) {
  background: rgba(139, 148, 158, 0.12);
  color: var(--bright);
  font-weight: 600;
  white-space: nowrap;
}
.doc-body :deep(strong) { color: var(--bright); }

.analyze-box {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(88, 166, 255, 0.35);
  border-radius: var(--radius-md);
  background: var(--blue-bg);
}
.analyze-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.analyze-body {
  font-size: 13px;
  line-height: 1.55;
  color: var(--bright);
}
.analyze-body :deep(h4) {
  margin: 0 0 6px;
  font-size: 13px;
}
.analyze-body :deep(.md-li) { margin: 2px 0; }
.analyze-body :deep(p) { margin: 0 0 4px; }
.analyze-body :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 6px 0;
  font-size: 12px;
}
.analyze-body :deep(.md-table th),
.analyze-body :deep(.md-table td) {
  border: 1px solid var(--border);
  padding: 4px 6px;
}
</style>
