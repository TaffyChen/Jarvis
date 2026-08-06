<template>
  <div class="review-page">
    <aside class="review-list panel-card">
      <div class="review-list-head">
        <h3>盘面简报</h3>
        <div class="muted">按日聚合 · 版本只追加</div>
      </div>
      <button class="btn btn-primary review-today-btn" :disabled="loading" @click="generateLive">
        {{ loading ? '生成中…' : '采集盘面生成新版' }}
      </button>
      <div v-if="!days.length" class="review-list-empty muted">还没有简报。盘中也可多次生成。</div>
      <button
        v-for="d in days"
        :key="d.date"
        type="button"
        :class="['review-list-item', { active: selectedDate === d.date }]"
        @click="openDay(d.date)"
      >
        <span class="review-list-date">
          {{ d.date }}
          <span v-if="d.hasFinal" class="final-pill">定稿</span>
        </span>
        <span class="review-list-headline">{{ d.headline || '（无标题）' }}</span>
        <span class="review-list-meta muted">{{ d.versionCount }} 版 · {{ formatHm(d.latestAt) }}</span>
      </button>
    </aside>

    <section class="review-detail panel-card">
      <div class="panel-head">
        <div>
          <h3>{{ selectedDate || '盘面简报' }}</h3>
          <div class="muted">
            每次生成冻结当时快照；旧版保留供对照决策。收盘后可「标为定稿」。
          </div>
        </div>
        <div class="review-actions">
          <button class="btn" :disabled="loading" @click="previewLive">预览当前盘面</button>
          <button
            class="btn"
            :disabled="loading || !current?.id"
            @click="regenFromCurrent"
          >基于本版快照再生成</button>
          <button
            class="btn"
            :disabled="loading || !current?.id || current?.isFinal"
            @click="markFinal"
          >标为当日定稿</button>
          <button class="btn btn-primary" :disabled="loading" @click="generateLive">
            采集盘面生成新版
          </button>
        </div>
      </div>

      <div v-if="error" class="error-banner">{{ error }}</div>
      <div v-if="warning" class="muted" style="margin-bottom:10px">{{ warning }}</div>

      <div v-if="livePreview" class="live-box">
        <div class="live-title">当前盘面预览（未保存 · 点「采集盘面生成新版」才会追加）</div>
        <div class="review-snap">
          <div class="review-chip">{{ livePreview.date }}</div>
          <div class="review-chip">{{ livePreview.positionCap?.text || '仓位—' }}</div>
          <div class="review-chip">
            ↑{{ livePreview.market?.breadth?.up ?? '—' }}
            ↓{{ livePreview.market?.breadth?.down ?? '—' }}
          </div>
        </div>
      </div>

      <div v-if="versions.length" class="version-bar">
        <button
          v-for="v in versions"
          :key="v.id"
          type="button"
          :class="['version-chip', { active: current?.id === v.id, final: v.isFinal }]"
          @click="openVersion(v.id)"
        >
          {{ formatHm(v.createdAt) || `#${v.id}` }}
          <span v-if="v.isFinal">·定稿</span>
        </button>
      </div>

      <div v-if="!current && !loading" class="empty">
        左侧选某日，或直接采集生成。同日可多版，不会覆盖历史。
      </div>

      <template v-if="current">
        <div class="review-snap">
          <div class="review-chip">#{{ current.id }} · {{ formatTs(current.createdAt) }}</div>
          <div v-if="current.isFinal" class="review-chip final-chip">定稿</div>
          <div class="review-chip">{{ current.snapshot?.positionCap?.text || '仓位—' }}</div>
          <div class="review-chip">
            ↑{{ current.snapshot?.market?.breadth?.up ?? '—' }}
            ↓{{ current.snapshot?.market?.breadth?.down ?? '—' }}
            <span v-if="current.snapshot?.market?.sentimentRetreat"> · 情绪退潮</span>
          </div>
          <div
            v-for="s in (current.snapshot?.sectors?.topByInflow || []).slice(0, 3)"
            :key="'in-' + s.sectorName"
            class="review-chip up"
          >
            流入 {{ s.sectorName }} {{ s.netInflow }}亿
          </div>
        </div>

        <div class="review-body md-body" v-html="html" />

        <div class="comment-box">
          <div class="comment-title">本版批注（基于本版再生成时会读）</div>
          <div v-if="!(current.comments || []).length" class="muted" style="font-size:12px;margin-bottom:8px">
            例如：「验证窗口失败，叙事降级」「已按此版减仓」
          </div>
          <div v-for="(c, i) in current.comments || []" :key="i" class="comment-item">
            <span class="muted">{{ formatTs(c.ts) }}</span>
            <span>{{ c.text }}</span>
          </div>
          <div class="comment-form">
            <input
              v-model.trim="commentDraft"
              class="search-input"
              placeholder="写下纠偏 / 验证 / 操作备注…"
              @keydown.enter.prevent="submitComment"
            >
            <button class="btn btn-sm btn-primary" :disabled="!commentDraft || commenting" @click="submitComment">
              添加批注
            </button>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { renderAssistantHtml } from '../utils/markdown'

const loading = ref(false)
const commenting = ref(false)
const error = ref('')
const warning = ref('')
const days = ref([])
const selectedDate = ref('')
const versions = ref([])
const current = ref(null)
const livePreview = ref(null)
const commentDraft = ref('')

const html = computed(() => renderAssistantHtml(current.value?.reportMd || ''))

onMounted(async () => {
  await refreshDays()
  if (days.value[0]) await openDay(days.value[0].date)
})

function formatTs(iso) {
  if (!iso) return ''
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}

function formatHm(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return ''
  }
}

async function refreshDays() {
  const r = await api.reviewDays()
  days.value = r.days || []
}

async function openDay(date, preferId = null) {
  error.value = ''
  livePreview.value = null
  selectedDate.value = date
  try {
    const r = await api.reviewDay(date)
    versions.value = r.day?.versions || []
    const pick = preferId
      || r.day?.finalId
      || versions.value[0]?.id
    if (pick) await openVersion(pick)
    else current.value = null
  } catch (e) {
    error.value = e.message || '加载失败'
    versions.value = []
    current.value = null
  }
}

async function openVersion(id) {
  try {
    const r = await api.reviewVersion(id)
    current.value = r.version || null
  } catch (e) {
    error.value = e.message || '版本加载失败'
    current.value = null
  }
}

async function previewLive() {
  error.value = ''
  try {
    const r = await api.reviewSnapshot()
    livePreview.value = r.snapshot || null
    ElMessage.success('已预览当前盘面（未写入）')
  } catch (e) {
    error.value = e.message || '预览失败'
  }
}

async function generateLive() {
  loading.value = true
  error.value = ''
  warning.value = ''
  livePreview.value = null
  try {
    const r = await api.reviewGenerate({ refreshSnapshot: true })
    warning.value = r.report?.warning || ''
    const ver = r.version
    await refreshDays()
    if (ver?.date) await openDay(ver.date, ver.id)
    ElMessage.success('已追加新版简报')
  } catch (e) {
    error.value = e.response?.data?.error || e.message || '生成失败'
  } finally {
    loading.value = false
  }
}

async function regenFromCurrent() {
  if (!current.value?.id) return
  loading.value = true
  error.value = ''
  warning.value = ''
  try {
    const r = await api.reviewGenerate({
      refreshSnapshot: false,
      baseVersionId: current.value.id,
    })
    warning.value = r.report?.warning || ''
    const ver = r.version
    await refreshDays()
    if (ver?.date) await openDay(ver.date, ver.id)
    ElMessage.success('已基于本版快照追加新版（旧版保留）')
  } catch (e) {
    error.value = e.response?.data?.error || e.message || '生成失败'
  } finally {
    loading.value = false
  }
}

async function markFinal() {
  if (!current.value?.id) return
  try {
    const r = await api.reviewMarkFinal(current.value.id)
    current.value = r.version || current.value
    await refreshDays()
    if (selectedDate.value) {
      const day = await api.reviewDay(selectedDate.value)
      versions.value = day.day?.versions || []
    }
    ElMessage.success('已标为当日定稿')
  } catch (e) {
    error.value = e.response?.data?.error || e.message || '标记失败'
  }
}

async function submitComment() {
  if (!current.value?.id || !commentDraft.value) return
  commenting.value = true
  try {
    const r = await api.reviewComment(current.value.id, commentDraft.value)
    current.value = r.version || current.value
    commentDraft.value = ''
    if (selectedDate.value) {
      const day = await api.reviewDay(selectedDate.value)
      versions.value = day.day?.versions || []
    }
    ElMessage.success('批注已保存到本版')
  } catch (e) {
    error.value = e.response?.data?.error || e.message || '批注失败'
  } finally {
    commenting.value = false
  }
}
</script>

<style scoped>
.review-page {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 12px;
  align-items: stretch;
  min-height: 520px;
}
.review-list, .review-detail {
  display: flex; flex-direction: column; min-height: 0;
}
.review-list-head h3 { margin: 0 0 2px; font-size: 15px; color: var(--bright); }
.review-today-btn { margin: 10px 0 12px; width: 100%; justify-content: center; }
.review-list-empty { font-size: 12px; padding: 8px 0; }
.review-list-item {
  width: 100%; text-align: left;
  display: flex; flex-direction: column; gap: 2px;
  padding: 8px 10px; margin-bottom: 6px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  background: var(--neutral-soft); color: var(--text); cursor: pointer;
}
.review-list-item:hover { border-color: var(--blue); }
.review-list-item.active { border-color: var(--blue); background: var(--blue-bg); }
.review-list-date { font-size: 12px; font-weight: 600; color: var(--bright); display: flex; gap: 6px; align-items: center; }
.final-pill, .final-chip {
  font-size: 10px; font-weight: 600; color: var(--blue);
  border: 1px solid rgba(88,166,255,0.4); border-radius: 4px; padding: 0 4px;
}
.review-list-headline {
  font-size: 12px; color: var(--muted); line-height: 1.35;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.review-list-meta { font-size: 11px; }
.panel-head {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  margin-bottom: 12px; flex-wrap: wrap;
}
.panel-head h3 { margin: 0 0 4px; font-size: 16px; color: var(--bright); }
.review-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.live-box {
  border: 1px dashed var(--border); border-radius: var(--radius-md);
  padding: 10px 12px; margin-bottom: 12px; background: var(--neutral-soft);
}
.live-title { font-size: 12px; color: var(--muted); margin-bottom: 8px; }
.version-bar { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.version-chip {
  font-size: 12px; padding: 4px 8px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--neutral-soft); color: var(--muted); cursor: pointer;
}
.version-chip:hover { border-color: var(--blue); }
.version-chip.active { border-color: var(--blue); color: var(--bright); background: var(--blue-bg); }
.version-chip.final { border-color: rgba(88,166,255,0.45); }
.review-snap { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.review-chip {
  font-size: 12px; padding: 3px 8px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--neutral-soft); color: var(--muted);
}
.review-chip.up { color: var(--red); border-color: rgba(248,81,73,0.35); }
.review-body {
  border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 14px 16px; background: var(--card-bg); line-height: 1.6; font-size: 13px;
  flex: 1; overflow: auto;
}
.comment-box { margin-top: 12px; }
.comment-title { font-size: 13px; font-weight: 600; color: var(--bright); margin-bottom: 6px; }
.comment-item {
  display: flex; flex-direction: column; gap: 2px;
  font-size: 12px; padding: 6px 0; border-bottom: 1px solid var(--border);
}
.comment-form { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.comment-form .search-input { flex: 1; min-width: 180px; max-width: none; }
@media (max-width: 900px) {
  .review-page { grid-template-columns: 1fr; }
}
</style>
