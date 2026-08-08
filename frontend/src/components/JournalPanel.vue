<template>
  <div class="journal-page">
    <div class="panel-card">
      <div class="panel-head">
        <div>
          <h3>纪律日记</h3>
          <div class="muted">告警留痕：当时什么票、什么级别、系统建议什么、你实际怎么做。不改持仓、不下单。</div>
        </div>
        <span class="muted">{{ countLabel }}</span>
      </div>

      <div class="journal-toolbar">
        <div class="search-wrap">
          <input
            v-model.trim="search"
            class="search-input"
            placeholder="搜索代码 / 名称 / 告警 / 动作 / 备注"
          >
          <button
            v-if="search"
            type="button"
            class="search-clear"
            title="清空"
            aria-label="清空搜索"
            @click="search = ''"
          >×</button>
        </div>
        <div class="tabs">
          <button
            v-for="t in tabs"
            :key="t.id"
            :class="['tab', { active: level === t.id }]"
            @click="level = t.id"
          >
            {{ t.label }}
            <span class="tab-count">{{ counts[t.id] ?? 0 }}</span>
          </button>
        </div>
      </div>

      <div v-if="!allRows.length" class="empty">还没有日记。首页预警或卡片上点「记日记」即可写入。</div>
      <div v-else-if="!rows.length" class="empty">没有匹配的日记，试试换关键词或级别。</div>
      <div v-else class="journal-list">
        <article v-for="(j, i) in rows" :key="j.id || (j.ts + '-' + i)" class="journal-item">
          <div class="journal-meta">
            <span>{{ formatTime(j.ts) }}</span>
            <b>{{ j.name || j.code || '—' }}</b>
            <span v-if="j.code && j.name" class="muted">{{ j.code }}</span>
            <span v-if="j.level" :class="['lvl', j.level]">{{ j.level }}</span>
            <span v-if="j.lamps != null" class="muted">当时 {{ j.lamps }} 红</span>
          </div>
          <div class="journal-body">
            <div>{{ j.msg || '—' }} → <b>{{ j.action || '—' }}</b></div>
            <div v-if="j.note" class="journal-note">备注：{{ j.note }}</div>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'

const dash = useDashboardStore()
const search = ref('')
const level = ref('all')
const tabs = [
  { id: 'all', label: '全部' },
  { id: 'danger', label: '危险' },
  { id: 'warning', label: '警告' },
  { id: 'info', label: '信息' },
]

const allRows = computed(() => dash.journal || [])

const counts = computed(() => {
  const rows = allRows.value
  return {
    all: rows.length,
    danger: rows.filter((j) => normLevel(j.level) === 'danger').length,
    warning: rows.filter((j) => normLevel(j.level) === 'warning').length,
    info: rows.filter((j) => normLevel(j.level) === 'info').length,
  }
})

const rows = computed(() => allRows.value.filter((j) => matchJournal(j, search.value, level.value)))

const countLabel = computed(() => {
  if (!allRows.value.length) return '共 0 条'
  if (rows.value.length === allRows.value.length) return `共 ${rows.value.length} 条`
  return `显示 ${rows.value.length} / ${allRows.value.length} 条`
})

function normLevel(raw) {
  const text = String(raw || '').trim().toLowerCase()
  if (text === 'warn') return 'warning'
  return text
}

function matchJournal(j, q, lvl) {
  if (lvl && lvl !== 'all' && normLevel(j.level) !== lvl) return false
  const needle = String(q || '').trim().toLowerCase()
  if (!needle) return true
  const code = String(j.code || '').toLowerCase()
  const bare = code.replace(/^(sh|sz)/, '')
  const hay = [code, bare, j.name, j.msg, j.action, j.note, j.level]
    .map((x) => String(x || '').toLowerCase())
    .join(' ')
  if (hay.includes(needle)) return true
  const digits = needle.replace(/\D/g, '')
  return Boolean(digits) && hay.includes(digits)
}

function formatTime(iso) {
  if (!iso) return '--'
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}
</script>

<style scoped>
.journal-page { display: flex; flex-direction: column; gap: 12px; }
.panel-head {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  margin-bottom: 12px;
}
.panel-head h3 { margin: 0 0 4px; font-size: 16px; color: var(--bright); }
.journal-toolbar {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px 12px;
  margin-bottom: 12px;
}
.journal-toolbar .search-wrap { max-width: 360px; }
.journal-list { display: flex; flex-direction: column; gap: 8px; }
.journal-item {
  border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 10px 12px; background: var(--neutral-soft);
}
.journal-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px;
  font-size: 12px; color: var(--muted); margin-bottom: 6px;
}
.journal-meta b { color: var(--bright); font-size: 13px; }
.journal-body { font-size: 13px; line-height: 1.55; color: var(--text); }
.journal-note { margin-top: 4px; color: var(--muted); }
.lvl {
  text-transform: uppercase; font-size: 11px; font-weight: 600;
  padding: 1px 6px; border-radius: 999px; border: 1px solid var(--border);
}
.lvl.danger { color: var(--red); border-color: var(--red); background: var(--red-bg); }
.lvl.warning, .lvl.warn { color: var(--orange); border-color: var(--orange); background: var(--orange-bg); }
.lvl.info { color: var(--blue); border-color: var(--blue); background: var(--blue-bg); }
</style>
