<template>
  <div class="panel-card">
    <div class="panel-head">
      <div>
        <h3>竞价异动榜 · TOP10</h3>
        <div class="muted" v-if="meta">
          扫描 {{ meta.scanned }} · {{ formatTime(meta.lastUpdate) }}
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
            <th>委比%</th><th>量比</th><th>PE</th><th>评分</th><th>信号</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!rows.length">
            <td colspan="11" style="text-align:center;color:var(--muted);padding:24px">点击「扫描刷新」</td>
          </tr>
          <tr v-for="(row, i) in rows" :key="row.code">
            <td><span :class="['screen-rank', i===0?'top1':i===1?'top2':i===2?'top3':'other']">{{ i+1 }}</span></td>
            <td>{{ row.name }}</td>
            <td>{{ row.code?.replace(/^(sh|sz)/, '') }}</td>
            <td>{{ fmt(row.price) }}</td>
            <td :class="chgClass(row.changePct)">{{ fmtPct(row.changePct) }}</td>
            <td :class="(row.weibi || 0) < 0 ? 'down' : 'up'">{{ fmt(row.weibi, 1) }}</td>
            <td>{{ fmt(row.liangbi, 1) }}</td>
            <td>{{ fmt(row.pe, 1) }}</td>
            <td><b>{{ row.score }}</b></td>
            <td>
              <span v-for="(s, j) in (row.signals || []).slice(0, 3)" :key="j" class="sig-pill">{{ s }}</span>
            </td>
            <td><button class="btn btn-sm btn-primary" @click="$emit('add', row)">加入</button></td>
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
