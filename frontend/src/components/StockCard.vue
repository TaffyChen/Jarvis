<template>
  <div :class="['stock-card', rankClass]">
    <div class="card-top">
      <div class="card-left">
        <span :class="['rank', idx < 3 ? 'top' : '']">{{ idx + 1 }}</span>
        <div>
          <span class="name">{{ card.name }}</span>
          <span class="code">{{ card.rawCode || card.code }}</span>
          <div class="badge-row">
            <span class="badge badge-sector">{{ card.sector }}</span>
            <span v-if="card.pos" class="badge badge-hold">持仓</span>
            <span :class="['badge', 'badge-' + card.ratingClass]">{{ card.rating }}</span>
            <span
              :class="['badge', card.riskCleared ? 'badge-ok' : card.a?.riskOk === false ? 'badge-bad' : 'badge-info']"
            >{{ card.riskCleared ? '利空已复核' : card.a?.riskOk === false ? '利空未过' : '待复核' }}</span>
            <span v-if="card.stale" class="badge badge-warn">分析待更新</span>
          </div>
        </div>
      </div>
      <div>
        <div :class="['price', chgClass(card.q?.changePct)]">{{ fmt(card.q?.price) }}</div>
        <div :class="['price-chg', chgClass(card.q?.changePct)]">{{ fmtPct(card.q?.changePct) }}</div>
      </div>
    </div>

    <div class="sparkline" v-html="card.sparkHtml || '<span class=muted>无K线</span>'"></div>
    <div class="muted" v-if="card.k?.ma20">
      <span :style="{ color: card.belowMA20 ? 'var(--red)' : 'var(--green)' }">
        {{ card.belowMA20 ? '▼破20日线' : '▲20日线上方' }}({{ fmt(card.k.ma20) }})
      </span>
      <span v-if="card.k.ma60"> · 60日线({{ fmt(card.k.ma60) }})</span>
    </div>

    <div v-if="card.type === 'etf' && card.etf" class="muted" style="margin-top:6px">
      净值{{ card.etf.nav ?? '--' }} | 规模{{ card.etf.scale || '--' }}
      <span v-if="card.etf.holdings"><br>持仓: {{ card.etf.holdings }}</span>
    </div>

    <div class="metrics">
      <div><span>PE</span> {{ fmt(peVal, 1) }}</div>
      <div><span>PB</span> {{ fmt(card.q?.pb, 2) }}</div>
      <div><span>委比</span> <b :class="(card.q?.weibi || 0) < 0 ? 'down' : 'up'">{{ fmt(card.q?.weibi, 1) }}%</b></div>
      <div><span>20日</span> <b :class="chgClass(card.k?.change20d)">{{ fmtPct(card.k?.change20d) }}</b></div>
    </div>

    <div v-if="card.gateBlocked" class="gate-hint">评分已达可买入，但利空门禁拦截为观察</div>
    <div v-for="(x, i) in (card.analysis || [])" :key="i" :class="['analysis-item', x.type]">{{ x.text }}</div>
    <div class="reason" v-if="card.reason">{{ card.reason }}</div>
    <div class="notes" v-if="card.notes">{{ card.notes }}</div>

    <div v-if="card.pos" :class="['pnl', card.pnl >= 0 ? 'profit' : 'loss']">
      持仓 {{ card.pos.shares }}股 | 成本{{ Number(card.pos.buyPrice).toFixed(3) }}
      | 盈亏{{ card.pnl >= 0 ? '+' : '' }}{{ card.pnl.toFixed(0) }}
      ({{ card.pnlPct >= 0 ? '+' : '' }}{{ card.pnlPct.toFixed(2) }}%)
    </div>
    <div v-for="(al, i) in card.cardAlerts" :key="'a'+i" :class="['card-alert', al.level]">
      <span>⚠ {{ al.msg }} → {{ al.action }}</span>
      <button class="btn btn-sm btn-ghost" @click="$emit('journal', al)">记日记</button>
    </div>

    <div class="card-actions">
      <button class="btn btn-sm btn-success" @click="$emit('review', card.code, true)">利空通过</button>
      <button class="btn btn-sm btn-danger" @click="$emit('review', card.code, false)">利空未过</button>
      <button class="btn btn-sm btn-primary" @click="$emit('edit-position', card)">
        {{ card.pos ? '改持仓' : '+ 持仓' }}
      </button>
    </div>

    <div class="score-row">
      <span class="muted">综合评分{{ card.liveScore != null ? ' · 实时' : '' }}</span>
      <div class="score-bar">
        <div class="score-fill" :style="{ width: Math.min(card.score, 100) + '%', background: scoreColor(card.score) }"></div>
      </div>
      <b :style="{ color: scoreColor(card.score) }">{{ card.score }}</b>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  card: { type: Object, required: true },
  idx: { type: Number, default: 0 },
})
defineEmits(['review', 'edit-position', 'journal'])

const rankClass = computed(() => (
  props.idx === 0 ? 'rank-1' : props.idx === 1 ? 'rank-2' : props.idx === 2 ? 'rank-3' : ''
))
const peVal = computed(() => props.card.q?.peTTM || props.card.q?.pe)

function fmt(v, d = 2) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return '--'
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
function scoreColor(s) {
  if (s >= 50) return 'var(--green)'
  if (s >= 30) return 'var(--orange)'
  if (s >= 15) return 'var(--blue)'
  return 'var(--red)'
}
</script>
