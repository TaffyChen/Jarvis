<template>
  <div class="panel-card">
    <div class="panel-head">
      <div>
        <h3>盘后选股池 · TOP10</h3>
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
    <div style="overflow:auto">
      <table class="screen-table">
        <thead>
          <tr>
            <th>#</th><th>名称</th><th>代码</th><th>现价</th><th>涨跌%</th>
            <th>PE</th><th>20日%</th><th>MA20</th><th>评分</th><th>信号</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length">
            <td colspan="11" style="text-align:center;color:var(--muted);padding:24px">点击「扫描刷新」</td>
          </tr>
          <tr v-for="(row, i) in rows" :key="row.code" :class="{ dimmed: row.flags?.buyDiscouraged }">
            <td><span :class="['screen-rank', i===0?'top1':i===1?'top2':i===2?'top3':'other']">{{ i+1 }}</span></td>
            <td>
              {{ row.name }}
              <span v-if="row.flags?.inPosition" class="flag-pill">持仓</span>
            </td>
            <td>{{ row.code?.replace(/^(sh|sz)/, '') }}</td>
            <td>{{ fmt(row.price) }}</td>
            <td :class="chgClass(row.changePct)">{{ fmtPct(row.changePct) }}</td>
            <td>{{ fmt(row.pe, 1) }}</td>
            <td :class="chgClass(row.change20d)">{{ fmtPct(row.change20d) }}</td>
            <td :class="row.aboveMA20 ? 'up' : 'down'">{{ row.aboveMA20 ? '上方' : '下方' }}</td>
            <td><b>{{ row.score }}</b></td>
            <td>
              <span
                v-for="(s, j) in (row.signals || []).slice(0, 4)"
                :key="j"
                :class="['sig-pill', warnSig(s) ? 'warn' : '']"
              >{{ s }}</span>
            </td>
            <td>
              <button
                class="btn btn-sm btn-primary"
                :title="row.flags?.buyDiscouraged ? '纪律提示：今日不宜新开，加入仅作观察' : ''"
                @click="$emit('add', row)"
              >加入</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  rows: { type: Array, default: () => [] },
  meta: { type: Object, default: null },
  loading: Boolean,
})
defineEmits(['refresh', 'add'])

function warnSig(s) {
  return /不宜新开|破20|放量滞|放量下跌|破开盘/.test(String(s || ''))
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
.discipline-banner {
  margin-top: 6px; font-size: 12px; color: var(--red, #f85149);
  padding: 4px 8px; border-radius: var(--radius-md);
  border: 1px solid rgba(248,81,73,0.35); background: rgba(248,81,73,0.08);
}
.flag-pill {
  margin-left: 4px; font-size: 10px; color: var(--blue);
  border: 1px solid rgba(88,166,255,0.4); border-radius: 4px; padding: 0 4px;
}
.dimmed { opacity: 0.72; }
.sig-pill.warn { color: var(--red, #f85149); border-color: rgba(248,81,73,0.35); }
</style>
