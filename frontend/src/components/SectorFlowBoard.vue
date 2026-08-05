<template>
  <div class="flow-board">
    <div class="flow-hero">
      <div>
        <div class="flow-kicker">MARKET FLOW · DUAL RANK</div>
        <h3>板块主力资金双向榜</h3>
        <div class="muted">净流入 Top15 + 净流出 Top15 · {{ data?.source || '--' }} · {{ fmtTime(data?.lastUpdate) }}</div>
      </div>
    </div>

    <div class="flow-cards">
      <div class="flow-card inflow">
        <span>最大流入</span>
        <strong>{{ summary.topSector || '--' }}</strong>
        <em :class="numClass(summary.topNetInflow)">
          {{ fmtE(summary.topNetInflow) }} 亿
          <small>{{ fmtPct(summary.topChangePct) }}</small>
        </em>
      </div>
      <div class="flow-card mid">
        <span>市场广度</span>
        <strong>{{ summary.positiveCount || 0 }} 流入 / {{ summary.negativeCount || 0 }} 流出</strong>
        <em>{{ summary.total || 0 }} 个板块</em>
      </div>
      <div class="flow-card outflow">
        <span>最大流出</span>
        <strong>{{ summary.bottomSector || '--' }}</strong>
        <em :class="numClass(summary.bottomNetInflow)">
          {{ fmtE(summary.bottomNetInflow) }} 亿
          <small>{{ fmtPct(summary.bottomChangePct) }}</small>
        </em>
      </div>
    </div>

    <div v-if="inflowRows.length || outflowRows.length" class="flow-dual">
      <section class="flow-col">
        <div class="flow-col-title inflow">主力净流入榜 TOP 15</div>
        <div class="flow-list">
          <article v-for="(r, i) in inflowRows" :key="'in-' + r.sectorCode" class="flow-row">
            <span :class="['screen-rank', i === 0 ? 'top1' : i === 1 ? 'top2' : i === 2 ? 'top3' : 'other']">
              {{ String(i + 1).padStart(2, '0') }}
            </span>
            <div class="flow-main">
              <div class="flow-name-line">
                <b>{{ r.sectorName }}</b>
                <span class="flow-status hot">{{ statusOf(r) }}</span>
              </div>
              <div class="flow-bar">
                <i class="in" :style="{ width: barWidth(r.netInflow, maxAbsIn) }" />
              </div>
            </div>
            <div class="flow-nums">
              <strong :class="numClass(r.netInflow)">{{ fmtE(r.netInflow) }}</strong>
              <small :class="numClass(r.changePct)">{{ fmtPct(r.changePct) }}</small>
            </div>
          </article>
        </div>
      </section>

      <section class="flow-col">
        <div class="flow-col-title outflow">主力净流出榜 TOP 15</div>
        <div class="flow-list">
          <article v-for="(r, i) in outflowRows" :key="'out-' + r.sectorCode" class="flow-row">
            <span class="screen-rank other">{{ String(i + 1).padStart(2, '0') }}</span>
            <div class="flow-main">
              <div class="flow-name-line">
                <b>{{ r.sectorName }}</b>
                <span class="flow-status cold">{{ statusOf(r) }}</span>
              </div>
              <div class="flow-bar">
                <i class="out" :style="{ width: barWidth(Math.abs(r.netInflow), maxAbsOut) }" />
              </div>
            </div>
            <div class="flow-nums">
              <strong :class="numClass(r.netInflow)">{{ fmtE(r.netInflow) }}</strong>
              <small :class="numClass(r.changePct)">{{ fmtPct(r.changePct) }}</small>
            </div>
          </article>
        </div>
      </section>
    </div>
    <div v-else class="empty">暂无板块资金流数据</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, default: () => ({}) },
})

const summary = computed(() => props.data?.summary || {})
const allRows = computed(() => props.data?.list || [])
const inflowRows = computed(() => allRows.value.filter((r) => r.netInflow > 0).slice(0, 15))
const outflowRows = computed(() => [...allRows.value].filter((r) => r.netInflow < 0).sort((a, b) => a.netInflow - b.netInflow).slice(0, 15))
const maxAbsIn = computed(() => Math.max(...inflowRows.value.map((r) => Math.abs(r.netInflow)), 0.01))
const maxAbsOut = computed(() => Math.max(...outflowRows.value.map((r) => Math.abs(r.netInflow)), 0.01))

function statusOf(row) {
  if (row.netInflow > 0 && row.delta5m > 0) return '主动吸筹'
  if (row.netInflow > 0) return '流入放缓'
  if (row.netInflow < 0 && row.delta5m < 0) return '资金流出'
  if (row.netInflow < 0) return '流出放缓'
  return '观望'
}

function barWidth(value, max) {
  const pct = Math.max(8, Math.min(100, (Math.abs(Number(value) || 0) / max) * 100))
  return `${pct}%`
}

function fmtE(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}`
}

function fmtPct(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}

function numClass(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}

function fmtTime(iso) {
  if (!iso) return '--'
  try {
    return new Date(iso).toLocaleTimeString('zh-CN')
  } catch {
    return iso
  }
}
</script>

<style scoped>
.flow-board {
  display: grid;
  gap: 12px;
}

.flow-kicker {
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
  margin-bottom: 4px;
}

.flow-hero h3 {
  margin: 0 0 4px;
  color: var(--bright);
  font-size: 18px;
}

.flow-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.flow-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--card-bg);
  padding: 12px 14px;
  box-shadow: var(--shadow-sm);
}

.flow-card span {
  display: block;
  font-size: 12px;
  color: var(--muted);
}

.flow-card strong {
  display: block;
  margin: 6px 0 4px;
  color: var(--bright);
  font-size: 16px;
}

.flow-card em {
  font-style: normal;
  font-weight: 700;
  font-size: 14px;
}

.flow-card em small {
  margin-left: 8px;
  font-weight: 600;
}

.flow-card.inflow { border-color: rgba(248, 81, 73, 0.35); }
.flow-card.outflow { border-color: rgba(63, 185, 80, 0.35); }

.flow-dual {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.flow-col {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--card-bg);
  padding: 12px;
  box-shadow: var(--shadow-sm);
  min-width: 0;
}

.flow-col-title {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 10px;
  color: var(--bright);
}

.flow-col-title.inflow { color: var(--red); }
.flow-col-title.outflow { color: var(--green); }

.flow-list {
  display: grid;
  gap: 8px;
}

.flow-row {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 78px;
  gap: 8px;
  align-items: center;
}

.flow-name-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.flow-name-line b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--bright);
  font-size: 13px;
}

.flow-status {
  flex-shrink: 0;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--muted);
}

.flow-status.hot {
  color: var(--red);
  border-color: rgba(248, 81, 73, 0.35);
  background: var(--red-bg);
}

.flow-status.cold {
  color: var(--green);
  border-color: rgba(63, 185, 80, 0.35);
  background: var(--green-bg);
}

.flow-bar {
  height: 6px;
  border-radius: 999px;
  background: var(--neutral-soft, rgba(139, 148, 158, 0.16));
  overflow: hidden;
  margin-top: 4px;
}

.flow-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.flow-bar i.in { background: var(--red); }
.flow-bar i.out { background: var(--green); }

.flow-nums {
  text-align: right;
}

.flow-nums strong {
  display: block;
  font-size: 13px;
}

.flow-nums small {
  font-size: 11px;
}

@media (max-width: 1100px) {
  .flow-cards,
  .flow-dual {
    grid-template-columns: 1fr;
  }
}
</style>
