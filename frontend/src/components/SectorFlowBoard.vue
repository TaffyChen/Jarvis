<template>
  <div class="flow-board">
    <div class="flow-hero">
      <div>
        <div class="flow-kicker">SECTOR FLOW · AMOUNT × STRENGTH</div>
        <h3>板块主力资金</h3>
        <div class="muted">
          {{ data?.source || '东方财富' }} · {{ fmtTime(data?.lastUpdate) }}
          · 流入 {{ summary.positiveCount || 0 }} / 流出 {{ summary.negativeCount || 0 }}
          <template v-if="summary.divergenceCount"> · 背离 {{ summary.divergenceCount }}</template>
          <template v-if="summary.historyMinutes != null">
            · 历史约 {{ summary.historyMinutes }} 分
          </template>
        </div>
        <p class="flow-disclaimer">
          {{ data?.disclaimer || '主力净流入为估算口径；净流入率反映资金浓度，宜与绝对金额对照看。' }}
        </p>
      </div>
      <div class="flow-mode" role="group" aria-label="排序方式">
        <button type="button" :class="{ active: mode === 'amount' }" @click="mode = 'amount'">按金额</button>
        <button type="button" :class="{ active: mode === 'strength' }" @click="mode = 'strength'">按强度</button>
      </div>
    </div>

    <div class="flow-cards">
      <div class="flow-card inflow">
        <span>金额流入 Top</span>
        <strong>{{ summary.topSector || '--' }}</strong>
        <em :class="numClass(summary.topNetInflow)">
          {{ fmtE(summary.topNetInflow) }} 亿
          <small>{{ fmtPct(summary.topChangePct) }}</small>
        </em>
      </div>
      <div class="flow-card mid">
        <span>强度（净流入率）Top</span>
        <strong>{{ summary.topStrengthSector || '--' }}</strong>
        <em :class="numClass(summary.topStrength)">{{ fmtStrength(summary.topStrength) }}</em>
      </div>
      <div class="flow-card outflow">
        <span>金额流出 Top</span>
        <strong>{{ summary.bottomSector || '--' }}</strong>
        <em :class="numClass(summary.bottomNetInflow)">
          {{ fmtE(summary.bottomNetInflow) }} 亿
          <small>{{ fmtPct(summary.bottomChangePct) }}</small>
        </em>
      </div>
    </div>

    <div v-if="leftRows.length || rightRows.length" class="flow-dual">
      <section class="flow-col">
        <div class="flow-col-title inflow">{{ leftTitle }}</div>
        <div class="flow-list">
          <article
            v-for="(r, i) in leftRows"
            :key="'L-' + r.sectorCode"
            :class="['flow-row', { active: selected?.sectorCode === r.sectorCode, diverge: !!r.divergence }]"
            @click="selectRow(r)"
          >
            <span :class="['screen-rank', i === 0 ? 'top1' : i === 1 ? 'top2' : i === 2 ? 'top3' : 'other']">
              {{ String(i + 1).padStart(2, '0') }}
            </span>
            <div class="flow-main">
              <div class="flow-name-line">
                <b>{{ r.sectorName }}</b>
                <span :class="['flow-status', paceClass(r)]">{{ paceLabel(r) }}</span>
                <span v-if="r.divergence" class="flow-diverge">{{ divergeLabel(r.divergence) }}</span>
              </div>
              <div class="flow-meta">
                <span :class="numClass(r.delta5m)">5m {{ fmtDelta(r.delta5m) }}</span>
                <span :class="numClass(r.delta15m)">15m {{ fmtDelta(r.delta15m) }}</span>
                <span :class="numClass(r.delta30m)">30m {{ fmtDelta(r.delta30m) }}</span>
                <span :class="numClass(r.changePct)">{{ fmtPct(r.changePct) }}</span>
              </div>
              <div class="flow-bar">
                <i class="in" :style="{ width: barWidth(metricValue(r), maxAbsLeft) }" />
              </div>
            </div>
            <div class="flow-nums">
              <strong :class="numClass(primaryMetric(r))">{{ primaryText(r) }}</strong>
              <small :class="numClass(secondaryMetric(r))">{{ secondaryText(r) }}</small>
            </div>
          </article>
        </div>
      </section>

      <section class="flow-col">
        <div class="flow-col-title outflow">{{ rightTitle }}</div>
        <div class="flow-list">
          <article
            v-for="(r, i) in rightRows"
            :key="'R-' + r.sectorCode"
            :class="['flow-row', { active: selected?.sectorCode === r.sectorCode, diverge: !!r.divergence }]"
            @click="selectRow(r)"
          >
            <span class="screen-rank other">{{ String(i + 1).padStart(2, '0') }}</span>
            <div class="flow-main">
              <div class="flow-name-line">
                <b>{{ r.sectorName }}</b>
                <span :class="['flow-status', paceClass(r)]">{{ paceLabel(r) }}</span>
                <span v-if="r.divergence" class="flow-diverge">{{ divergeLabel(r.divergence) }}</span>
              </div>
              <div class="flow-meta">
                <span :class="numClass(r.delta5m)">5m {{ fmtDelta(r.delta5m) }}</span>
                <span :class="numClass(r.delta15m)">15m {{ fmtDelta(r.delta15m) }}</span>
                <span :class="numClass(r.delta30m)">30m {{ fmtDelta(r.delta30m) }}</span>
                <span :class="numClass(r.changePct)">{{ fmtPct(r.changePct) }}</span>
              </div>
              <div class="flow-bar">
                <i class="out" :style="{ width: barWidth(Math.abs(metricValue(r)), maxAbsRight) }" />
              </div>
            </div>
            <div class="flow-nums">
              <strong :class="numClass(primaryMetric(r))">{{ primaryText(r) }}</strong>
              <small :class="numClass(secondaryMetric(r))">{{ secondaryText(r) }}</small>
            </div>
          </article>
        </div>
      </section>
    </div>
    <div v-else class="empty">暂无板块资金流数据</div>

    <div v-if="selected" class="flow-detail">
      <div class="flow-detail-head">
        <div>
          <h4>{{ selected.sectorName }}</h4>
          <div class="muted">
            净流入 {{ fmtE(selected.netInflow) }}亿 · 强度 {{ fmtStrength(selected.strength) }}
            · 涨跌 {{ fmtPct(selected.changePct) }}
            <template v-if="selected.divergence"> · {{ divergeLabel(selected.divergence) }}</template>
          </div>
        </div>
        <button type="button" class="btn btn-sm btn-ghost" @click="selected = null">关闭</button>
      </div>
      <div class="flow-windows">
        <div class="flow-win">
          <span>约 5 分</span>
          <strong :class="numClass(selected.delta5m)">{{ fmtE(selected.delta5m) }}亿</strong>
        </div>
        <div class="flow-win">
          <span>约 15 分</span>
          <strong :class="numClass(selected.delta15m)">{{ fmtE(selected.delta15m) }}亿</strong>
        </div>
        <div class="flow-win">
          <span>约 30 分</span>
          <strong :class="numClass(selected.delta30m)">{{ fmtE(selected.delta30m) }}亿</strong>
        </div>
        <div class="flow-win">
          <span>节奏</span>
          <strong>{{ paceLabel(selected) }}</strong>
        </div>
      </div>
      <div class="flow-spark">
        <div class="flow-spark-head">
          <span>盘中累计净流入（亿）</span>
          <span class="muted" v-if="sparkMeta">{{ sparkMeta }}</span>
        </div>
        <svg
          v-if="spark.path"
          class="flow-spark-svg"
          viewBox="0 0 320 64"
          preserveAspectRatio="none"
          aria-label="板块资金曲线"
        >
          <line x1="0" :y1="spark.zeroY" x2="320" :y2="spark.zeroY" class="spark-zero" />
          <path :d="spark.area" class="spark-area" :class="spark.tone" />
          <path :d="spark.path" class="spark-line" :class="spark.tone" fill="none" />
        </svg>
        <div v-else class="muted flow-spark-empty">
          曲线样本不足（重启或刚启动后需轮询积累约 5～15 分钟）
        </div>
      </div>
      <div class="flow-detail-stats">
        <span>超大单流入 {{ fmtE(selected.leaderInflow) }}亿</span>
        <span>超大单流出 {{ fmtE(selected.leaderOutflow) }}亿</span>
      </div>
      <div v-if="relatedItems.length" class="flow-related">
        <div class="flow-related-title">自选 / 持仓映射（{{ relatedItems.length }}）</div>
        <div class="flow-related-list">
          <div v-for="it in relatedItems" :key="it.code" class="flow-related-row">
            <div>
              <b>{{ it.name }}</b>
              <span class="muted">{{ it.rawCode || it.code }} · {{ it.sector }}</span>
            </div>
            <div class="flow-related-nums">
              <span :class="chgClass(it.changePct)">{{ fmtPrice(it.price) }} {{ fmtPct(it.changePct) }}</span>
              <span v-if="it.inPosition" class="badge badge-hold">持仓</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="muted flow-related-empty">
        自选里暂无与「{{ selected.sectorName }}」明显相关的标的（板块标签模糊匹配）。
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { sectorMatch } from '../utils/signals'

const props = defineProps({
  data: { type: Object, default: () => ({}) },
  items: { type: Array, default: () => [] },
  quotes: { type: Object, default: () => ({}) },
  positions: { type: Object, default: () => ({}) },
})

const mode = ref('strength') // 默认按强度，对齐纪律「看浓度」
const selected = ref(null)

const summary = computed(() => props.data?.summary || {})
const allRows = computed(() => props.data?.list || [])

const leftTitle = computed(() => (
  mode.value === 'strength' ? '净流入率 TOP 15（浓度）' : '主力净流入 TOP 15（金额）'
))
const rightTitle = computed(() => (
  mode.value === 'strength' ? '净流入率靠后 TOP 15' : '主力净流出 TOP 15（金额）'
))

const leftRows = computed(() => {
  const list = allRows.value
  if (mode.value === 'strength') {
    return [...list].sort((a, b) => (b.strength || 0) - (a.strength || 0)).slice(0, 15)
  }
  return list.filter((r) => r.netInflow > 0).slice(0, 15)
})

const rightRows = computed(() => {
  const list = allRows.value
  if (mode.value === 'strength') {
    return [...list].sort((a, b) => (a.strength || 0) - (b.strength || 0)).slice(0, 15)
  }
  return [...list].filter((r) => r.netInflow < 0).sort((a, b) => a.netInflow - b.netInflow).slice(0, 15)
})

const maxAbsLeft = computed(() => Math.max(...leftRows.value.map((r) => Math.abs(metricValue(r))), 0.01))
const maxAbsRight = computed(() => Math.max(...rightRows.value.map((r) => Math.abs(metricValue(r))), 0.01))

watch(() => props.data?.lastUpdate, () => {
  if (!selected.value) return
  const next = allRows.value.find((r) => r.sectorCode === selected.value.sectorCode)
  if (next) selected.value = next
})

function selectRow(row) {
  selected.value = selected.value?.sectorCode === row.sectorCode ? null : row
}

function metricValue(r) {
  return mode.value === 'strength' ? Number(r.strength) || 0 : Number(r.netInflow) || 0
}
function primaryMetric(r) {
  return mode.value === 'strength' ? r.strength : r.netInflow
}
function secondaryMetric(r) {
  return mode.value === 'strength' ? r.netInflow : r.strength
}
function primaryText(r) {
  return mode.value === 'strength' ? fmtStrength(r.strength) : `${fmtE(r.netInflow)}亿`
}
function secondaryText(r) {
  return mode.value === 'strength' ? `${fmtE(r.netInflow)}亿` : `强度 ${fmtStrength(r.strength)}`
}

function paceLabel(row) {
  const p = row?.pace
  if (p === 'in_accel') return '流入加速'
  if (p === 'in_decel') return '流入减速'
  if (p === 'in_hold') return '流入持稳'
  if (p === 'out_accel') return '流出加速'
  if (p === 'out_decel') return '流出减速'
  if (p === 'out_hold') return '流出持稳'
  // 兼容旧缓存
  if (row?.netInflow > 0 && row?.delta5m > 0) return '流入加速'
  if (row?.netInflow > 0) return '流入持稳'
  if (row?.netInflow < 0 && row?.delta5m < 0) return '流出加速'
  if (row?.netInflow < 0) return '流出持稳'
  return '观望'
}

function paceClass(row) {
  const p = row?.pace || ''
  if (p.startsWith('in_') || (row?.netInflow > 0)) return 'hot'
  if (p.startsWith('out_') || (row?.netInflow < 0)) return 'cold'
  return ''
}

function divergeLabel(kind) {
  if (kind === 'price_up_flow_out') return '价涨资出'
  if (kind === 'price_down_flow_in') return '价跌资进'
  return '背离'
}

const relatedItems = computed(() => {
  const name = selected.value?.sectorName
  if (!name) return []
  const out = []
  for (const it of props.items || []) {
    if (!sectorMatch(it.sector, name)) continue
    const q = props.quotes?.[it.code] || {}
    out.push({
      code: it.code,
      rawCode: String(it.code || '').replace(/^(sh|sz)/i, ''),
      name: it.name || q.name || it.code,
      sector: it.sector,
      price: q.price,
      changePct: q.changePct,
      inPosition: !!props.positions?.[it.code],
    })
  }
  out.sort((a, b) => Number(b.inPosition) - Number(a.inPosition) || (b.changePct || 0) - (a.changePct || 0))
  return out
})

const spark = computed(() => {
  const series = selected.value?.series || []
  if (series.length < 2) return { path: '', area: '', zeroY: 32, tone: '' }
  const vals = series.map((p) => Number(p.v)).filter((n) => Number.isFinite(n))
  if (vals.length < 2) return { path: '', area: '', zeroY: 32, tone: '' }
  const w = 320
  const h = 64
  const padY = 6
  const min = Math.min(...vals, 0)
  const max = Math.max(...vals, 0)
  const span = max - min || 1
  const yAt = (v) => padY + ((max - v) / span) * (h - padY * 2)
  const xAt = (i) => (i / (vals.length - 1)) * w
  const pts = vals.map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`)
  const path = `M ${pts.join(' L ')}`
  const zeroY = yAt(0)
  const area = `${path} L ${w},${h} L 0,${h} Z`
  const last = vals[vals.length - 1]
  const tone = last > 0 ? 'up' : last < 0 ? 'down' : ''
  return { path, area, zeroY, tone }
})

const sparkMeta = computed(() => {
  const series = selected.value?.series || []
  if (series.length < 2) return ''
  const first = series[0]?.t
  const last = series[series.length - 1]?.t
  if (!first || !last) return `${series.length} 点`
  try {
    const mins = Math.max(0, Math.round((new Date(last) - new Date(first)) / 60000))
    return `${series.length} 点 · 约 ${mins} 分`
  } catch {
    return `${series.length} 点`
  }
})

function barWidth(value, max) {
  const pct = Math.max(8, Math.min(100, (Math.abs(Number(value) || 0) / max) * 100))
  return `${pct}%`
}
function fmtE(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}`
}
function fmtDelta(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}`
}
function fmtPct(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}
function fmtStrength(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}
function fmtPrice(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || !n) return '--'
  return n.toFixed(2)
}
function numClass(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}
function chgClass(v) {
  return numClass(v)
}
function fmtTime(iso) {
  if (!iso) return '--'
  try { return new Date(iso).toLocaleTimeString('zh-CN') } catch { return iso }
}
</script>

<style scoped>
.flow-board { display: grid; gap: 12px; }
.flow-hero {
  display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; flex-wrap: wrap;
}
.flow-kicker {
  font-size: 11px; letter-spacing: 0.12em; color: var(--muted); margin-bottom: 4px;
}
.flow-hero h3 { margin: 0 0 4px; color: var(--bright); font-size: 18px; }
.flow-disclaimer {
  margin: 8px 0 0; font-size: 12px; color: var(--muted); line-height: 1.45; max-width: 720px;
}
.flow-mode {
  display: inline-flex; border: 1px solid var(--border); border-radius: var(--radius-md);
  overflow: hidden; background: var(--card-bg); flex-shrink: 0;
}
.flow-mode button {
  border: 0; background: transparent; color: var(--muted);
  font-size: 12px; padding: 6px 12px; cursor: pointer;
}
.flow-mode button.active {
  background: var(--blue-bg); color: var(--blue); font-weight: 600;
}

.flow-cards {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px;
}
.flow-card {
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  background: var(--card-bg); padding: 12px 14px; box-shadow: var(--shadow-sm);
}
.flow-card span { display: block; font-size: 12px; color: var(--muted); }
.flow-card strong { display: block; margin: 6px 0 4px; color: var(--bright); font-size: 16px; }
.flow-card em { font-style: normal; font-weight: 700; font-size: 14px; }
.flow-card em small { margin-left: 8px; font-weight: 600; }
.flow-card.inflow { border-color: rgba(248, 81, 73, 0.35); }
.flow-card.outflow { border-color: rgba(63, 185, 80, 0.35); }

.flow-dual { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.flow-col {
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  background: var(--card-bg); padding: 12px; box-shadow: var(--shadow-sm); min-width: 0;
}
.flow-col-title { font-size: 13px; font-weight: 700; margin-bottom: 10px; color: var(--bright); }
.flow-col-title.inflow { color: var(--red); }
.flow-col-title.outflow { color: var(--green); }
.flow-list { display: grid; gap: 8px; }

.flow-row {
  display: grid; grid-template-columns: 28px minmax(0, 1fr) 88px; gap: 8px;
  align-items: center; padding: 6px 6px; border-radius: 8px; cursor: pointer;
  border: 1px solid transparent;
}
.flow-row:hover { background: var(--hover-soft); }
.flow-row.active { border-color: var(--blue); background: var(--blue-bg); }
.flow-row.diverge { box-shadow: inset 3px 0 0 var(--orange); }

.flow-name-line {
  display: flex; align-items: center; gap: 6px; min-width: 0; flex-wrap: wrap;
}
.flow-name-line b {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--bright); font-size: 13px; max-width: 120px;
}
.flow-status {
  flex-shrink: 0; font-size: 10px; padding: 1px 6px; border-radius: 999px;
  border: 1px solid var(--border); color: var(--muted);
}
.flow-status.hot {
  color: var(--red); border-color: rgba(248, 81, 73, 0.35); background: var(--red-bg);
}
.flow-status.cold {
  color: var(--green); border-color: rgba(63, 185, 80, 0.35); background: var(--green-bg);
}
.flow-diverge {
  font-size: 10px; padding: 1px 6px; border-radius: 999px;
  color: var(--orange); border: 1px solid rgba(210, 153, 34, 0.4); background: var(--orange-bg);
}
.flow-meta {
  display: flex; flex-wrap: wrap; gap: 8px; margin-top: 3px;
  font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums;
}
.flow-bar {
  height: 5px; border-radius: 999px; margin-top: 4px;
  background: var(--neutral-soft, rgba(139, 148, 158, 0.16)); overflow: hidden;
}
.flow-bar i { display: block; height: 100%; border-radius: inherit; }
.flow-bar i.in { background: var(--red); }
.flow-bar i.out { background: var(--green); }
.flow-nums { text-align: right; font-variant-numeric: tabular-nums; }
.flow-nums strong { display: block; font-size: 13px; }
.flow-nums small { font-size: 11px; color: var(--muted); }

.flow-detail {
  border: 1px solid var(--border); border-radius: var(--radius-lg);
  background: var(--card-bg); padding: 12px 14px; box-shadow: var(--shadow-sm);
}
.flow-detail-head {
  display: flex; justify-content: space-between; gap: 12px; align-items: flex-start;
}
.flow-detail-head h4 { margin: 0 0 4px; color: var(--bright); font-size: 15px; }
.flow-detail-stats {
  display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px;
  font-size: 12px; color: var(--muted);
}
.flow-windows {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px;
  margin-top: 10px;
}
.flow-win {
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px;
  background: var(--hover-soft, rgba(139, 148, 158, 0.08));
}
.flow-win span { display: block; font-size: 11px; color: var(--muted); }
.flow-win strong { display: block; margin-top: 4px; font-size: 14px; color: var(--bright); }
.flow-spark { margin-top: 12px; }
.flow-spark-head {
  display: flex; justify-content: space-between; gap: 8px; align-items: baseline;
  font-size: 12px; color: var(--bright); margin-bottom: 6px;
}
.flow-spark-svg {
  width: 100%; height: 64px; display: block;
  border: 1px solid var(--border); border-radius: 8px; background: var(--hover-soft, rgba(139, 148, 158, 0.06));
}
.spark-zero { stroke: var(--border); stroke-width: 1; stroke-dasharray: 3 3; }
.spark-line { stroke-width: 1.8; }
.spark-line.up { stroke: var(--red); }
.spark-line.down { stroke: var(--green); }
.spark-line:not(.up):not(.down) { stroke: var(--muted); }
.spark-area { opacity: 0.12; }
.spark-area.up { fill: var(--red); }
.spark-area.down { fill: var(--green); }
.spark-area:not(.up):not(.down) { fill: var(--muted); }
.flow-spark-empty { font-size: 12px; padding: 12px 0; }
.flow-related { margin-top: 12px; }
.flow-related-title { font-size: 12px; font-weight: 700; color: var(--bright); margin-bottom: 8px; }
.flow-related-list { display: grid; gap: 6px; }
.flow-related-row {
  display: flex; justify-content: space-between; gap: 10px; align-items: center;
  padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px;
}
.flow-related-row b { color: var(--bright); margin-right: 8px; }
.flow-related-nums { display: flex; align-items: center; gap: 8px; font-size: 12px; white-space: nowrap; }
.flow-related-empty { margin-top: 10px; font-size: 12px; }

@media (max-width: 1100px) {
  .flow-cards, .flow-dual { grid-template-columns: 1fr; }
  .flow-windows { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 640px) {
  .flow-windows { grid-template-columns: 1fr 1fr; }
}
</style>
