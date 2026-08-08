<template>
  <div
    :class="[
      'stock-card',
      rankClass,
      { 'has-danger': hasDanger, 'is-expanded': expanded },
    ]"
  >
    <div class="card-top">
      <div class="card-left">
        <span :class="['rank', idx < 3 ? 'top' : '']">{{ idx + 1 }}</span>
        <div class="card-title-block">
          <div class="card-title-line">
            <span class="name">{{ card.name }}</span>
            <span class="code">{{ card.rawCode || card.code }}</span>
          </div>
          <div class="badge-row">
            <span :class="['badge', 'badge-' + card.ratingClass]">{{ card.rating }}</span>
            <span
              :class="['badge', card.riskCleared ? 'badge-ok' : card.a?.riskOk === false ? 'badge-bad' : 'badge-info']"
            >{{ gateLabel }}</span>
            <span v-if="card.pos" class="badge badge-hold">持仓</span>
            <span v-if="card.stale" class="badge badge-warn">待更新</span>
            <span
              v-if="card.mainlineHit"
              :class="['badge', card.mainlineTone === 'ready' ? 'badge-mainline-ready' : 'badge-mainline']"
              :title="card.mainlineAction"
            >{{ card.mainlineTone === 'ready' ? '主线·可考虑' : '主线重合' }}</span>
            <span
              v-if="volumePhaseBadge"
              :class="['badge', volumePhaseBadge.cls]"
              :title="volumePhaseBadge.tip"
            >{{ volumePhaseBadge.text }}</span>
          </div>
        </div>
      </div>
      <div class="card-price-block">
        <div :class="['price', chgClass(card.q?.changePct)]">{{ fmt(card.q?.price) }}</div>
        <div :class="['price-chg', chgClass(card.q?.changePct)]">{{ fmtPct(card.q?.changePct) }}</div>
        <div class="card-score-inline" :style="{ color: scoreColor(card.score) }">
          {{ card.score }}
          <span class="muted">分</span>
        </div>
      </div>
    </div>

    <div class="sparkline card-spark" v-html="card.sparkHtml || ''"></div>

    <div v-if="card.pos" :class="['pnl', 'pnl-compact', card.pnl >= 0 ? 'profit' : 'loss']">
      <span>{{ card.pnlPct >= 0 ? '+' : '' }}{{ card.pnlPct.toFixed(2) }}%</span>
      <span>{{ card.pnl >= 0 ? '+' : '' }}{{ Math.round(card.pnl).toLocaleString('zh-CN') }}</span>
      <span class="pnl-meta">{{ card.pos.shares }}股 · 成本{{ Number(card.pos.buyPrice).toFixed(3) }}</span>
    </div>

    <div
      v-if="primaryAlert"
      :class="['card-alert', primaryAlert.level]"
    >
      <span>⚠ {{ primaryAlert.msg }} → {{ primaryAlert.action }}</span>
      <button class="btn btn-sm btn-ghost" @click.stop="$emit('journal', primaryAlert)">记日记</button>
    </div>

    <div v-if="card.gateBlocked" class="gate-hint">门禁拦截：{{ card.rating === '不追' ? '偏离过高降为不追' : '评分达可买入，仍为观察' }}</div>

    <div v-if="card.reasonLine && card.reasonLine !== '—'" class="card-reason" :title="card.reasonLine">
      {{ card.reasonLine }}
    </div>

    <div class="card-footer">
      <button type="button" class="card-more-btn" @click="expanded = !expanded">
        {{ expanded ? '收起详情' : '更多' }}
      </button>
      <div class="card-actions">
        <button class="btn btn-sm btn-ghost" title="利空通过" @click="$emit('review', card.code, true)">通过</button>
        <button class="btn btn-sm btn-ghost" title="利空未过" @click="$emit('review', card.code, false)">未过</button>
        <button class="btn btn-sm btn-primary" @click="$emit('edit-position', card)">
          {{ card.pos ? '改仓' : '+仓' }}
        </button>
      </div>
    </div>

    <div v-if="expanded" class="card-detail">
      <div class="badge-row detail-badges">
        <span class="badge badge-sector">{{ card.sector }}</span>
        <span v-if="card.k?.ma20" class="muted">
          <span :style="{ color: card.belowMA20 ? 'var(--orange)' : 'var(--muted)' }">
            {{ card.belowMA20 ? '破MA20' : 'MA20上方' }} {{ fmt(card.k.ma20) }}
          </span>
        </span>
      </div>
      <div class="metrics">
        <div><span>PE</span> {{ fmt(peVal, 1) }}</div>
        <div><span>PB</span> {{ fmt(card.q?.pb, 2) }}</div>
        <div><span>委比</span> <b :class="(card.q?.weibi || 0) < 0 ? 'down' : 'up'">{{ fmt(card.q?.weibi, 1) }}%</b></div>
        <div><span>20日</span> <b :class="chgClass(card.k?.change20d)">{{ fmtPct(card.k?.change20d) }}</b></div>
      </div>
      <div v-if="card.type === 'etf' && card.etf" class="muted">
        净值{{ card.etf.nav ?? '--' }} | 规模{{ card.etf.scale || '--' }}
      </div>
      <div v-if="card.levels" class="levels-row">
        <span :class="['level-chip', card.levels.stopHit ? 'hit' : '']">
          止损 {{ fmt(card.levels.stopLoss, 2) }}
          <template v-if="card.levels.distToStopPct != null">
            · 距{{ card.levels.distToStopPct >= 0 ? '+' : '' }}{{ card.levels.distToStopPct.toFixed(1) }}%
          </template>
        </span>
        <span :class="['level-chip tp', card.levels.takeHit ? 'hit-tp' : '']">
          止盈 {{ fmt(card.levels.takeProfit, 2) }}
          <template v-if="card.levels.distToTakePct != null">
            · 距{{ card.levels.distToTakePct >= 0 ? '+' : '' }}{{ card.levels.distToTakePct.toFixed(1) }}%
          </template>
        </span>
      </div>
      <div v-for="(x, i) in (card.analysis || [])" :key="'an'+i" :class="['analysis-item', x.type]">{{ x.text }}</div>
      <div class="reason" v-if="card.reason">{{ card.reason }}</div>
      <div class="notes" v-if="card.notes">{{ card.notes }}</div>
      <div
        v-for="(al, i) in extraAlerts"
        :key="'a'+i"
        :class="['card-alert', al.level]"
      >
        <span>⚠ {{ al.msg }} → {{ al.action }}</span>
        <button class="btn btn-sm btn-ghost" @click.stop="$emit('journal', al)">记日记</button>
      </div>
      <div class="score-row">
        <span class="muted">综合评分{{ card.liveScore != null ? ' · 实时' : '' }}</span>
        <div class="score-bar">
          <div class="score-fill" :style="{ width: Math.min(card.score, 100) + '%', background: scoreColor(card.score) }"></div>
        </div>
        <b :style="{ color: scoreColor(card.score) }">{{ card.score }}</b>
      </div>
      <div class="card-analyze-row">
        <button
          type="button"
          class="btn btn-sm btn-ghost"
          :disabled="analyzing"
          title="对照纪律与行情做短评，非买卖指令"
          @click="runAnalyze"
        >{{ analyzing ? '深析中…' : '深析' }}</button>
        <span class="muted analyze-hint">对照门禁/铁律 · 可选</span>
      </div>
      <div v-if="analyzeMd" class="card-analyze-box">
        <div class="card-analyze-head">
          <b>深析</b>
          <button type="button" class="btn btn-sm btn-ghost" @click="analyzeMd = ''">关闭</button>
        </div>
        <div class="card-analyze-body" v-html="renderMd(analyzeMd)"></div>
        <div v-if="analyzeHint" class="muted" style="font-size:11px;margin-top:4px">{{ analyzeHint }}</div>
      </div>
      <button class="btn btn-sm btn-ghost card-remove" @click="$emit('remove', card)">移出自选</button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { api } from '../api'
import { scoreColor } from '../utils/strategy'

const props = defineProps({
  card: { type: Object, required: true },
  idx: { type: Number, default: 0 },
})
defineEmits(['review', 'edit-position', 'journal', 'remove'])

const expanded = ref(false)
const analyzing = ref(false)
const analyzeMd = ref('')
const analyzeMode = ref('')

const analyzeHint = computed(() => {
  if (analyzeMode.value === 'llm') return '大模型短评 · 非买卖指令'
  if (analyzeMode.value === 'rules') return '未配置 LLM，仅规则摘要'
  return ''
})

function buildWhy(card) {
  const why = []
  if (card.rating) why.push(`当前评级 ${card.rating}`)
  if (card.score != null) why.push(`综合分 ${card.score}`)
  if (card.riskCleared) why.push('利空复核已通过')
  else if (card.a?.riskOk === false) why.push('利空未过')
  else why.push('利空待复核或已过期')
  if (card.belowMA20) why.push('现价破MA20')
  else if (card.k?.ma20 > 0) why.push('现价在MA20上方')
  if (card.pos) {
    why.push(`持仓浮盈 ${card.pnlPct >= 0 ? '+' : ''}${Number(card.pnlPct || 0).toFixed(2)}%`)
  }
  if (card.primaryAlert) why.push(`预警：${card.primaryAlert.msg}→${card.primaryAlert.action}`)
  if (card.mainlineHit) why.push(card.mainlineAction || '主线重合')
  if (card.gateBlocked) why.push('评分门禁拦截中')
  return why
}

async function runAnalyze() {
  const card = props.card
  if (!card?.code || analyzing.value) return
  analyzing.value = true
  analyzeMd.value = ''
  try {
    const row = {
      code: card.code,
      name: card.name,
      price: card.q?.price,
      changePct: card.q?.changePct,
      pe: card.q?.peTTM || card.q?.pe,
      liangbi: card.q?.liangbi,
      weibi: card.q?.weibi,
      ma20: card.k?.ma20,
      aboveMA20: card.k?.ma20 > 0 && card.q?.price > 0 ? card.q.price >= card.k.ma20 : null,
      change20d: card.k?.change20d,
      score: card.score,
      why: buildWhy(card),
      flags: {
        inWatch: true,
        inPosition: !!card.pos,
        belowMA20: !!card.belowMA20,
        buyDiscouraged: !!card.gateBlocked,
      },
    }
    const r = await api.screenAnalyze('quality', card.code, row)
    analyzeMd.value = r?.markdown || '（无内容）'
    analyzeMode.value = r?.mode || ''
  } catch (e) {
    analyzeMd.value = `深析失败：${e?.message || e}`
    analyzeMode.value = 'error'
  } finally {
    analyzing.value = false
  }
}

function renderMd(md) {
  const esc = String(md || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return esc
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h4>$1</h4>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm, '<div class="md-li">• $1</div>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
}

const rankClass = computed(() => (
  props.idx === 0 ? 'rank-1' : props.idx === 1 ? 'rank-2' : props.idx === 2 ? 'rank-3' : ''
))
const peVal = computed(() => props.card.q?.peTTM || props.card.q?.pe)
const gateLabel = computed(() => {
  if (props.card.riskCleared) return '已复核'
  if (props.card.a?.riskOk === false) return '未过'
  return '待复核'
})
const hasDanger = computed(() => (props.card.cardAlerts || []).some((a) => a.level === 'danger'))
const primaryAlert = computed(() => (props.card.cardAlerts || [])[0] || null)
const extraAlerts = computed(() => (props.card.cardAlerts || []).slice(1))

const volumePhaseBadge = computed(() => {
  const vp = props.card.volumePhase
  if (!vp?.id || vp.id === 'unknown') return null
  const conf = vp.conf === 'high' ? '高' : vp.conf === 'medium' ? '中' : '低'
  const cls = {
    distribute: 'badge-vp-out',
    markup: 'badge-vp-up',
    wash: 'badge-vp-wash',
    accumulate: 'badge-vp-acc',
  }[vp.id] || 'badge-info'
  return {
    text: `${vp.label}·${conf}`,
    tip: vp.tip || '量价阶段假说，非买卖指令',
    cls,
  }
})

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
</script>
