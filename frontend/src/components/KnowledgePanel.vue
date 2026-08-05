<template>
  <div class="kb-page">
    <div class="panel-card kb-status">
      <div class="panel-head">
        <div>
          <h3>知识库维护</h3>
          <div class="muted">
            原文在 <code>knowledge/</code> · 切块「标题路径 + 窗口 overlap」· 检索「向量 + 关键词 RRF + rerank」
          </div>
        </div>
        <div class="kb-actions">
          <button class="btn" :disabled="loading" @click="reload">刷新</button>
          <button class="btn btn-primary" :disabled="reindexing || !canReindex" @click="reindex">
            {{ reindexing ? '重建中…' : '重建索引' }}
          </button>
        </div>
      </div>
      <div class="kb-meta">
        <span>后端 {{ info.backend || '--' }}</span>
        <span>Embedding {{ embedLabel }}</span>
        <span>Rerank {{ rerankLabel }}</span>
        <span>文档 {{ (info.documents || []).length }}</span>
        <span>切块 {{ info.collectedChunks ?? '--' }} / 已索引 {{ info.chunks ?? '--' }}</span>
        <span>更新 {{ formatTime(info.updatedAt) }}</span>
        <span v-if="info.needsReindex" class="kb-warn">索引可能过期</span>
        <span v-else-if="info.ready" class="kb-ok">索引就绪</span>
      </div>
      <div class="kb-search-row">
        <input v-model="trialQuery" class="kb-input" placeholder="试检索：例如 五灯 / 主升第一天 / 持仓预警" @keydown.enter="trialSearch" />
        <button class="btn" :disabled="searching || !trialQuery.trim()" @click="trialSearch">试检索</button>
      </div>
      <div v-if="hits.length" class="kb-hits">
        <div v-for="(h, i) in hits" :key="i" class="kb-hit">
          <div class="kb-hit-head">
            <b>{{ h.source || 'unknown' }}</b>
            <span class="muted">score {{ h.score }}</span>
          </div>
          <div class="kb-hit-text">{{ h.text }}</div>
        </div>
      </div>
    </div>

    <div class="kb-workspace">
      <aside class="panel-card kb-list">
        <div class="kb-list-head">
          <h3>文档</h3>
          <button class="btn btn-sm btn-primary" @click="startCreate">新建</button>
        </div>
        <button
          v-for="doc in documents"
          :key="doc.path"
          :class="['kb-doc', { active: currentPath === doc.path, dirty: dirtyPath === doc.path }]"
          @click="openDoc(doc.path)"
        >
          <div class="kb-doc-name">{{ doc.path }}</div>
          <div class="muted">{{ formatSize(doc.bytes) }} · {{ formatTime(doc.updatedAt) }}</div>
        </button>
        <div v-if="!documents.length" class="empty">暂无 Markdown</div>
      </aside>

      <section class="panel-card kb-editor">
        <div v-if="creating" class="kb-new-row">
          <input v-model="newPath" class="kb-input" placeholder="文件名，如 自定义纪律.md" @keydown.enter="confirmCreate" />
          <button class="btn btn-primary" @click="confirmCreate">创建</button>
          <button class="btn" @click="cancelCreate">取消</button>
        </div>
        <template v-else-if="currentPath">
          <div class="kb-editor-head">
            <div>
              <h3>{{ currentPath }}</h3>
              <div class="muted">{{ dirty ? '未保存' : '已同步磁盘' }} · 保存后记得重建索引</div>
            </div>
            <div class="kb-actions">
              <button class="btn" :disabled="previewing" @click="preview">{{ previewing ? '切块中…' : '预览切块' }}</button>
              <button class="btn btn-primary" :disabled="saving || !dirty" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
              <button class="btn" :disabled="saving" @click="removeDoc">删除</button>
            </div>
          </div>
          <textarea v-model="content" class="kb-textarea" spellcheck="false" />
          <div v-if="previewChunks.length" class="kb-preview">
            <div class="muted">切块预览 · {{ previewChunks.length }} 段</div>
            <div v-for="c in previewChunks" :key="c.id" class="kb-chunk">
              <div class="kb-hit-head">
                <b>{{ c.meta?.heading || c.id }}</b>
                <span class="muted">{{ c.id }}</span>
              </div>
              <div class="kb-hit-text">{{ c.text }}</div>
            </div>
          </div>
        </template>
        <div v-else class="empty">选择左侧文档，或新建一篇纪律说明。</div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const reindexing = ref(false)
const previewing = ref(false)
const searching = ref(false)
const info = ref({})
const documents = ref([])
const currentPath = ref('')
const content = ref('')
const savedContent = ref('')
const previewChunks = ref([])
const creating = ref(false)
const newPath = ref('')
const trialQuery = ref('')
const hits = ref([])
const dirtyPath = ref('')

const dirty = computed(() => content.value !== savedContent.value)
const canReindex = computed(() => auth.can('kb.reindex'))
const embedLabel = computed(() => {
  const e = info.value.embedding || {}
  return `${e.backend || '--'}${e.model ? ' / ' + e.model : ''} · ${e.dim || '--'}d`
})
const rerankLabel = computed(() => {
  const r = info.value.rerank || {}
  if (!r.enabled) return '关闭'
  return r.model || 'on'
})

function formatTime(iso) {
  if (!iso) return '--'
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}
function formatSize(n) {
  const v = Number(n) || 0
  if (v < 1024) return `${v} B`
  return `${(v / 1024).toFixed(1)} KB`
}

async function reload() {
  loading.value = true
  try {
    const r = await api.kbStatus()
    info.value = r || {}
    documents.value = r?.documents || []
  } catch (e) {
    ElMessage.error('加载知识库失败：' + (e.response?.data?.detail || e.message || e))
  } finally {
    loading.value = false
  }
}

async function openDoc(path) {
  if (dirty.value && currentPath.value && currentPath.value !== path) {
    try {
      await ElMessageBox.confirm('当前文档未保存，切换将丢弃修改。', '未保存', {
        confirmButtonText: '丢弃并切换',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch { return }
  }
  creating.value = false
  try {
    const r = await api.kbDocument(path)
    currentPath.value = r.path
    content.value = r.content || ''
    savedContent.value = content.value
    previewChunks.value = []
    dirtyPath.value = ''
  } catch (e) {
    ElMessage.error('打开失败：' + (e.response?.data?.detail || e.message || e))
  }
}

function startCreate() {
  creating.value = true
  newPath.value = ''
  currentPath.value = ''
  content.value = ''
  savedContent.value = ''
  previewChunks.value = []
}

function cancelCreate() {
  creating.value = false
  newPath.value = ''
}

async function confirmCreate() {
  let path = (newPath.value || '').trim().replace(/\\/g, '/')
  if (!path) {
    ElMessage.warning('请输入文件名')
    return
  }
  if (!path.endsWith('.md')) path += '.md'
  try {
    await api.saveKbDocument(path, `# ${path.replace(/\.md$/, '')}\n\n`, true)
    creating.value = false
    await reload()
    await openDoc(path)
    ElMessage.success('已创建，编辑后保存并重建索引')
  } catch (e) {
    ElMessage.error('创建失败：' + (e.response?.data?.detail || e.message || e))
  }
}

async function save() {
  if (!currentPath.value) return
  saving.value = true
  try {
    await api.saveKbDocument(currentPath.value, content.value, false)
    savedContent.value = content.value
    dirtyPath.value = currentPath.value
    await reload()
    ElMessage.success('已保存到磁盘，请重建索引后对话才会用到新内容')
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message || e))
  } finally {
    saving.value = false
  }
}

async function removeDoc() {
  if (!currentPath.value) return
  try {
    await ElMessageBox.confirm(`删除 ${currentPath.value}？此操作不可撤销。`, '删除文档', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch { return }
  try {
    await api.deleteKbDocument(currentPath.value)
    currentPath.value = ''
    content.value = ''
    savedContent.value = ''
    previewChunks.value = []
    await reload()
    ElMessage.success('已删除，记得重建索引')
  } catch (e) {
    ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message || e))
  }
}

async function preview() {
  previewing.value = true
  try {
    const r = await api.previewKb({ path: currentPath.value, content: content.value })
    previewChunks.value = r.chunks || []
  } catch (e) {
    ElMessage.error('预览失败：' + (e.response?.data?.detail || e.message || e))
  } finally {
    previewing.value = false
  }
}

async function reindex() {
  reindexing.value = true
  try {
    const r = await api.reindex()
    dirtyPath.value = ''
    await reload()
    ElMessage.success(`索引已重建：${r.chunks} 个片段`)
  } catch (e) {
    ElMessage.error('重建失败：' + (e.response?.data?.detail || e.message || e))
  } finally {
    reindexing.value = false
  }
}

async function trialSearch() {
  const q = trialQuery.value.trim()
  if (!q) return
  searching.value = true
  try {
    const r = await api.searchKb(q, 5)
    hits.value = r.hits || []
    if (!hits.value.length) ElMessage.info('没有命中，可先重建索引再试')
  } catch (e) {
    ElMessage.error('检索失败：' + (e.response?.data?.detail || e.message || e))
  } finally {
    searching.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.kb-page { display: flex; flex-direction: column; gap: 12px; }
.kb-meta {
  display: flex; flex-wrap: wrap; gap: 10px 16px;
  font-size: 12px; color: var(--muted); margin-bottom: 10px;
}
.kb-ok { color: var(--green); }
.kb-warn { color: var(--orange); font-weight: 600; }
.kb-actions { display: flex; gap: 8px; flex-shrink: 0; }
.kb-search-row { display: flex; gap: 8px; }
.kb-input {
  flex: 1; min-width: 0;
  background: var(--chip-bg); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 8px 10px; font-size: 13px;
}
.kb-hits, .kb-preview { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
.kb-hit, .kb-chunk {
  border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 8px 10px; background: var(--neutral-soft);
}
.kb-hit-head { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 4px; font-size: 12px; }
.kb-hit-text { font-size: 12px; line-height: 1.55; white-space: pre-wrap; color: var(--text); }
.kb-workspace { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 12px; min-height: 560px; }
.kb-list { padding: 12px; overflow: auto; }
.kb-list-head, .kb-editor-head, .kb-new-row {
  display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 10px;
}
.kb-list-head h3, .kb-editor-head h3 { margin: 0; font-size: 15px; color: var(--bright); }
.kb-doc {
  display: block; width: 100%; text-align: left;
  border: 1px solid transparent; background: transparent; color: inherit;
  border-radius: var(--radius-md); padding: 8px 10px; cursor: pointer; margin-bottom: 4px;
}
.kb-doc:hover { background: var(--hover-soft); }
.kb-doc.active { border-color: var(--blue); background: var(--blue-bg); }
.kb-doc.dirty .kb-doc-name::after { content: ' · 待重建'; color: var(--orange); font-size: 11px; }
.kb-doc-name { font-size: 13px; color: var(--bright); word-break: break-all; }
.kb-editor { display: flex; flex-direction: column; min-height: 560px; }
.kb-textarea {
  flex: 1; min-height: 360px; resize: vertical;
  background: var(--md-pre-bg); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 12px; font-size: 13px; line-height: 1.6;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
@media (max-width: 960px) {
  .kb-workspace { grid-template-columns: 1fr; }
}
</style>
