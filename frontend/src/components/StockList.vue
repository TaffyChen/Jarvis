<template>
  <div class="stock-list-wrap">
    <table class="screen-table stock-list-table">
      <thead>
        <tr>
          <th class="col-rank sticky-col">#</th>
          <th class="col-symbol sticky-col sticky-symbol">标的</th>
          <th
            class="sortable num"
            title="按现价排序"
            @click="toggleSort('price')"
          >现价 <span class="sort-mark">{{ mark('price') }}</span></th>
          <th
            class="sortable num"
            title="按涨跌幅排序"
            @click="toggleSort('changePct')"
          >涨跌 <span class="sort-mark">{{ mark('changePct') }}</span></th>
          <th
            class="sortable num"
            title="按综合评分排序（默认）"
            @click="toggleSort('score')"
          >评分 <span class="sort-mark">{{ mark('score') }}</span></th>
          <th
            class="sortable num"
            title="按持仓盈亏比例排序"
            @click="toggleSort('pnlPct')"
          >盈亏% <span class="sort-mark">{{ mark('pnlPct') }}</span></th>
          <th
            class="sortable num"
            title="按浮动盈亏金额排序"
            @click="toggleSort('pnl')"
          >盈亏额 <span class="sort-mark">{{ mark('pnl') }}</span></th>
          <th
            class="sortable num"
            title="按持仓股数排序"
            @click="toggleSort('shares')"
          >持仓 <span class="sort-mark">{{ mark('shares') }}</span></th>
          <th>评级</th>
          <th>门禁</th>
          <th class="col-reason">理由</th>
          <th class="col-risk">提醒</th>
          <th class="col-actions">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(card, idx) in sortedCards"
          :key="card.code"
          :class="{ 'row-alert': card.primaryAlert?.level === 'danger' }"
        >
          <td class="col-rank sticky-col">
            <span :class="['screen-rank', idx === 0 ? 'top1' : idx === 1 ? 'top2' : idx === 2 ? 'top3' : 'other']">
              {{ idx + 1 }}
            </span>
          </td>
          <td class="col-symbol sticky-col sticky-symbol list-symbol" :title="symbolTitle(card)">
            <div class="list-name">{{ card.name }}</div>
            <div class="list-code">{{ card.rawCode || card.code }}</div>
          </td>
          <td class="num" :class="chgClass(card.q?.changePct)">{{ fmt(card.q?.price) }}</td>
          <td class="num" :class="chgClass(card.q?.changePct)">{{ fmtPct(card.q?.changePct) }}</td>
          <td class="num">
            <b :style="{ color: scoreColor(card.score) }">{{ card.score }}</b>
          </td>
          <td class="num">
            <template v-if="card.pos">
              <span :class="card.pnlPct >= 0 ? 'up' : 'down'" class="list-pnl-pct">
                {{ card.pnlPct >= 0 ? '+' : '' }}{{ card.pnlPct.toFixed(2) }}%
              </span>
            </template>
            <span v-else class="muted">—</span>
          </td>
          <td class="num">
            <template v-if="card.pos">
              <span :class="card.pnl >= 0 ? 'up' : 'down'" class="list-pnl-amt">
                {{ card.pnl >= 0 ? '+' : '' }}{{ Math.round(card.pnl).toLocaleString('zh-CN') }}
              </span>
            </template>
            <span v-else class="muted">—</span>
          </td>
          <td class="num list-shares">
            <template v-if="card.pos">
              <span :title="`成本 ${Number(card.pos.buyPrice).toFixed(3)}`">{{ card.pos.shares }}股</span>
            </template>
            <span v-else class="muted">—</span>
          </td>
          <td>
            <span :class="['badge', 'badge-' + card.ratingClass]">{{ card.rating || '--' }}</span>
            <span
              v-if="card.mainlineHit"
              :class="['badge', card.mainlineTone === 'ready' ? 'badge-mainline-ready' : 'badge-mainline']"
              :title="card.mainlineAction"
            >{{ card.mainlineTone === 'ready' ? '主线·可考虑' : '主线' }}</span>
            <span
              v-if="volumePhaseOf(card)"
              :class="['badge', volumePhaseOf(card).cls]"
              :title="volumePhaseOf(card).tip"
            >{{ volumePhaseOf(card).text }}</span>
          </td>
          <td>
            <span
              :class="['badge', card.riskCleared ? 'badge-ok' : card.a?.riskOk === false ? 'badge-bad' : 'badge-info']"
            >{{ card.riskCleared ? '已复核' : card.a?.riskOk === false ? '未过' : '待复核' }}</span>
          </td>
          <td class="col-reason">
            <div class="list-reason" :title="card.reasonLine || ''">{{ card.reasonLine || '—' }}</div>
          </td>
          <td class="col-risk">
            <div
              v-if="card.primaryAlert"
              :class="['list-alert-msg', card.primaryAlert.level]"
              :title="card.primaryAlert.msg"
            >⚠ {{ card.primaryAlert.msg }}</div>
            <span v-else class="muted">—</span>
          </td>
          <td class="col-actions list-actions">
            <button class="btn btn-sm btn-success" @click="$emit('review', card.code, true)">通过</button>
            <button class="btn btn-sm btn-danger" @click="$emit('review', card.code, false)">未过</button>
            <button class="btn btn-sm btn-primary" @click="$emit('edit-position', card)">
              {{ card.pos ? '改仓' : '+仓' }}
            </button>
            <button
              class="btn btn-sm btn-ghost"
              title="深析（对照纪律）"
              :disabled="analyzingCode === card.code"
              @click="runAnalyze(card)"
            >{{ analyzingCode === card.code ? '…' : '深析' }}</button>
            <button class="btn btn-sm btn-ghost" title="移出自选" @click="$emit('remove', card)">移除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="analyzeMd" class="list-analyze-box panel-card">
      <div class="list-analyze-head">
        <b>深析 · {{ analyzeTitle }}</b>
        <button type="button" class="btn btn-sm btn-ghost" @click="closeAnalyze">关闭</button>
      </div>
      <div class="list-analyze-body" v-html="renderMd(analyzeMd)"></div>
      <div v-if="analyzeHint" class="muted" style="font-size:11px;margin-top:6px">{{ analyzeHint }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { api } from '../api'
import { scoreColor } from '../utils/strategy'

const props = defineProps({
  cards: { type: Array, default: () => [] },
})
defineEmits(['review', 'edit-position', 'journal', 'remove'])

const analyzingCode = ref('')
const analyzeMd = ref('')
const analyzeTitle = ref('')
const analyzeMode = ref('')

const analyzeHint = computed(() => {
  if (analyzeMode.value === 'llm') return '大模型短评 · 非买卖指令'
  if (analyzeMode.value === 'rules') return '未配置 LLM，仅规则摘要'
  return ''
})

function closeAnalyze() {
  analyzeMd.value = ''
  analyzeTitle.value = ''
  analyzeMode.value = ''
}

function buildWhy(card) {
  const why = []
  if (card.rating) why.push(`当前评级 ${card.rating}`)
  if (card.score != null) why.push(`综合分 ${card.score}`)
  if (card.riskCleared) why.push('利空复核已通过')
  else if (card.a?.riskOk === false) why.push('利空未过')
  else why.push('利空待复核或已过期')
  if (card.belowMA20) why.push('破MA20')
  else if (card.k?.ma20 > 0) why.push('MA20上方')
  if (card.pos) why.push(`持仓浮盈 ${card.pnlPct >= 0 ? '+' : ''}${Number(card.pnlPct || 0).toFixed(2)}%`)
  if (card.primaryAlert) why.push(`预警：${card.primaryAlert.msg}`)
  if (card.mainlineHit) why.push(card.mainlineAction || '主线重合')
  return why
}

async function runAnalyze(card) {
  if (!card?.code || analyzingCode.value) return
  analyzingCode.value = card.code
  analyzeMd.value = ''
  analyzeTitle.value = `${card.name || card.code}`
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
      flags: { inWatch: true, inPosition: !!card.pos, belowMA20: !!card.belowMA20 },
    }
    const r = await api.screenAnalyze('quality', card.code, row)
    analyzeMd.value = r?.markdown || '（无内容）'
    analyzeMode.value = r?.mode || ''
  } catch (e) {
    analyzeMd.value = `深析失败：${e?.message || e}`
    analyzeMode.value = 'error'
  } finally {
    analyzingCode.value = ''
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
    .replace(/^- (.+)$/gm, '<div>• $1</div>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
}
/** @type {import('vue').Ref<null | 'price' | 'changePct' | 'score' | 'pnl' | 'pnlPct' | 'shares'>} */
const sortKey = ref(null)
/** @type {import('vue').Ref<'asc' | 'desc'>} */
const sortDir = ref('desc')

function mark(key) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'desc' ? '↓' : '↑'
}

function toggleSort(key) {
  if (sortKey.value !== key) {
    sortKey.value = key
    sortDir.value = 'desc'
    return
  }
  if (sortDir.value === 'desc') {
    sortDir.value = 'asc'
    return
  }
  sortKey.value = null
  sortDir.value = 'desc'
}

function sortValue(card, key) {
  if (key === 'price') return Number(card.q?.price) || 0
  if (key === 'changePct') return Number(card.q?.changePct) || 0
  if (key === 'score') return Number(card.score) || 0
  if (key === 'pnl') return card.pos ? Number(card.pnl) || 0 : null
  if (key === 'pnlPct') return card.pos ? Number(card.pnlPct) || 0 : null
  if (key === 'shares') return card.pos ? Number(card.pos.shares) || 0 : null
  return 0
}

const sortedCards = computed(() => {
  const list = props.cards.slice()
  const key = sortKey.value
  if (!key) return list
  const dir = sortDir.value === 'asc' ? 1 : -1
  list.sort((a, b) => {
    const va = sortValue(a, key)
    const vb = sortValue(b, key)
    if (va == null && vb == null) return (b.score || 0) - (a.score || 0)
    if (va == null) return 1
    if (vb == null) return -1
    if (va === vb) return (b.score || 0) - (a.score || 0)
    return va > vb ? dir : -dir
  })
  return list
})

function symbolTitle(card) {
  const parts = [card.name, card.rawCode || card.code]
  if (card.sector) parts.push(card.sector)
  if (card.pos) parts.push('持仓')
  return parts.filter(Boolean).join(' · ')
}

function volumePhaseOf(card) {
  const vp = card?.volumePhase
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
}

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

<style scoped>
.sortable {
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}
.sortable:hover { color: var(--blue); }
.sort-mark {
  font-size: 10px;
  color: var(--blue);
  font-weight: 700;
}
.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.col-rank {
  width: 40px;
  min-width: 40px;
  max-width: 40px;
  text-align: center;
  left: 0;
}
.col-symbol,
.sticky-symbol {
  width: 96px;
  min-width: 96px;
  max-width: 96px;
  left: 40px;
}
.sticky-col {
  position: sticky;
  background: var(--card-bg);
  z-index: 2;
}
thead .sticky-col {
  z-index: 5;
  top: 0;
}
.sticky-symbol {
  box-shadow: 4px 0 8px -4px rgba(0, 0, 0, 0.35);
}
:deep(tr:hover) > .sticky-col {
  background: var(--hover-soft);
}

.list-symbol {
  overflow: hidden;
}
.list-name {
  font-weight: 600;
  color: var(--bright);
  font-size: 13px;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.list-code {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.2;
  margin-top: 1px;
}

.list-pnl-pct {
  font-weight: 700;
  font-size: 13px;
}
.list-pnl-amt {
  font-weight: 600;
  font-size: 12px;
}
.list-shares {
  color: var(--bright);
  font-size: 12px;
}

.col-risk {
  min-width: 140px;
  max-width: 200px;
}
.col-reason {
  min-width: 160px;
  max-width: 240px;
}
.list-reason {
  font-size: 11px;
  line-height: 1.35;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: normal;
}
.list-alert-msg {
  font-size: 11px;
  line-height: 1.35;
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.list-alert-msg.danger { color: var(--red); }
.list-alert-msg.warning { color: var(--orange); }

.row-alert td.col-rank { box-shadow: inset 3px 0 0 var(--red); }

.col-actions { min-width: 200px; }
.list-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}
.list-actions .btn {
  transform: none !important;
  padding: 3px 8px;
}
.list-actions .btn:hover {
  transform: none !important;
}
</style>
