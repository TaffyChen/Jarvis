<template>
  <div class="stock-list-wrap">
    <table class="screen-table stock-list-table">
      <thead>
        <tr>
          <th>#</th>
          <th>标的</th>
          <th>板块</th>
          <th>评级</th>
          <th>现价</th>
          <th>涨跌</th>
          <th>MA20</th>
          <th>20日</th>
          <th>评分</th>
          <th>持仓</th>
          <th>风控</th>
          <th>利空</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(card, idx) in cards" :key="card.code" :class="{ 'row-alert': card.primaryAlert?.level === 'danger' }">
          <td>
            <span :class="['screen-rank', idx === 0 ? 'top1' : idx === 1 ? 'top2' : idx === 2 ? 'top3' : 'other']">
              {{ idx + 1 }}
            </span>
          </td>
          <td>
            <div class="list-name">{{ card.name }}</div>
            <div class="list-code">{{ card.rawCode || card.code }}</div>
          </td>
          <td><span class="badge badge-sector">{{ card.sector }}</span></td>
          <td><span :class="['badge', 'badge-' + card.ratingClass]">{{ card.rating || '--' }}</span></td>
          <td :class="chgClass(card.q?.changePct)">{{ fmt(card.q?.price) }}</td>
          <td :class="chgClass(card.q?.changePct)">{{ fmtPct(card.q?.changePct) }}</td>
          <td :class="card.belowMA20 ? 'down' : (card.k?.ma20 ? 'up' : '')">
            {{ card.k?.ma20 ? (card.belowMA20 ? '下方' : '上方') : '--' }}
          </td>
          <td :class="chgClass(card.k?.change20d)">{{ fmtPct(card.k?.change20d) }}</td>
          <td>
            <b :style="{ color: scoreColor(card.score) }">{{ card.score }}</b>
          </td>
          <td>
            <template v-if="card.pos">
              <div :class="card.pnl >= 0 ? 'up' : 'down'">
                {{ card.pnl >= 0 ? '+' : '' }}{{ card.pnl.toFixed(0) }}
                <span class="list-pnl-pct">{{ card.pnlPct >= 0 ? '+' : '' }}{{ card.pnlPct.toFixed(2) }}%</span>
              </div>
              <div class="list-code">{{ card.pos.shares }}股</div>
              <div v-if="card.levels" class="list-levels">
                止损{{ fmt(card.levels.stopLoss, 2) }}
                / 止盈{{ fmt(card.levels.takeProfit, 2) }}
              </div>
            </template>
            <span v-else class="muted">—</span>
          </td>
          <td class="list-risk">
            <div v-if="card.primaryAlert" :class="['list-alert-msg', card.primaryAlert.level]">
              ⚠ {{ card.primaryAlert.msg }}
            </div>
            <span v-else class="muted">—</span>
          </td>
          <td>
            <span
              :class="['badge', card.riskCleared ? 'badge-ok' : card.a?.riskOk === false ? 'badge-bad' : 'badge-info']"
            >{{ card.riskCleared ? '已复核' : card.a?.riskOk === false ? '未过' : '待复核' }}</span>
          </td>
          <td class="list-actions">
            <button class="btn btn-sm btn-success" @click="$emit('review', card.code, true)">通过</button>
            <button class="btn btn-sm btn-danger" @click="$emit('review', card.code, false)">未过</button>
            <button class="btn btn-sm btn-primary" @click="$emit('edit-position', card)">
              {{ card.pos ? '改仓' : '+仓' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({
  cards: { type: Array, default: () => [] },
})
defineEmits(['review', 'edit-position', 'journal'])

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

<style scoped>
.list-levels { font-size: 11px; color: var(--muted); margin-top: 2px; }
.list-risk { max-width: 180px; }
.list-alert-msg {
  font-size: 11px; line-height: 1.35;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.list-alert-msg.danger { color: var(--red); }
.list-alert-msg.warning { color: var(--orange); }
.row-alert td:first-child { box-shadow: inset 3px 0 0 var(--red); }
</style>
