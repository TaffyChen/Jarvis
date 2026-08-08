<template>
  <el-dialog :model-value="modelValue" title="添加标的" width="520px" @close="close">
    <el-form label-position="top">
      <el-form-item label="搜索股票 / ETF">
        <el-autocomplete
          v-model="form.keyword"
          :fetch-suggestions="querySearch"
          value-key="label"
          placeholder="输入名称或代码，如 美的 / 000333"
          style="width:100%"
          clearable
          @select="onSelect"
          @keyup.enter="peekQuote"
        />
      </el-form-item>
      <el-form-item label="完整代码">
        <el-input v-model="form.code" disabled />
      </el-form-item>
      <el-form-item label="名称">
        <el-input v-model="form.name" placeholder="可自动填充" />
      </el-form-item>
      <div style="display:flex;gap:12px">
        <el-form-item label="类型" style="flex:1">
          <el-select v-model="form.type" style="width:100%">
            <el-option label="个股" value="stock" />
            <el-option label="ETF" value="etf" />
          </el-select>
        </el-form-item>
        <el-form-item label="评级" style="flex:1">
          <el-select v-model="form.rating" style="width:100%">
            <el-option label="自动（按系统得分）" value="auto" />
            <el-option label="观察" value="观察" />
            <el-option label="不追" value="不追" />
            <el-option label="排除" value="排除" />
            <el-option label="可买入" value="可买入" />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="2" />
      </el-form-item>
      <div v-if="hint" class="muted">{{ hint }}</div>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">添加</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useDashboardStore } from '../stores/dashboard'
import { api } from '../api'
import { liveScoreFrom, ratingFromScore } from '../utils/strategy'

const props = defineProps({
  modelValue: Boolean,
  preset: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])

const dash = useDashboardStore()
const saving = ref(false)
const hint = ref('')
const form = reactive({
  keyword: '',
  code: '',
  name: '',
  type: 'stock',
  rating: 'auto',
  notes: '',
})

function close() {
  emit('update:modelValue', false)
}

function normalizeCode(raw) {
  const c = String(raw || '').trim().toLowerCase().replace(/^(sh|sz)/, '')
  if (!c) return ''
  if (/^(5|6|9)/.test(c) || /^11|^12/.test(c)) return 'sh' + c
  return 'sz' + c
}

async function querySearch(queryString, cb) {
  const q = String(queryString || '').trim()
  if (!q) {
    cb([])
    return
  }
  try {
    const r = await api.searchCodes(q)
    cb((r.results || []).map((row) => ({
      ...row,
      label: `${row.name}  ${String(row.code || '').replace(/^(sh|sz)/i, '')}`,
    })))
  } catch {
    cb([])
  }
}

function applyHit(hit) {
  form.code = hit.code || normalizeCode(hit.raw || form.keyword)
  form.name = hit.name || form.name
  form.type = hit.type || (/^(sh5|sz1)/.test(form.code) ? 'etf' : 'stock')
  form.keyword = hit.name ? `${hit.name}  ${form.code.replace(/^(sh|sz)/i, '')}` : form.keyword
  const q = dash.quotes[form.code]
  const k = dash.klines[form.code] || {}
  const score = liveScoreFrom(q, k, { code: form.code })
  hint.value = score != null
    ? `当前可得评分约 ${score} → ${ratingFromScore(score)}（加入后会拉最新行情）`
    : '保存后会加入自选并拉取最新行情'
}

function onSelect(item) {
  applyHit(item)
}

async function peekQuote() {
  if (form.code) {
    applyHit({ code: form.code, name: form.name, type: form.type })
    return
  }
  const q = String(form.keyword || '').trim()
  if (!q) return
  try {
    const r = await api.searchCodes(q)
    const hit = (r.results || [])[0]
    if (hit) {
      applyHit(hit)
      return
    }
  } catch { /* ignore */ }
  form.code = normalizeCode(q)
  if (!form.code) return
  applyHit({ code: form.code, name: dash.quotes[form.code]?.name || '' })
}

function reset() {
  form.keyword = ''
  form.code = ''
  form.name = ''
  form.type = 'stock'
  form.rating = 'auto'
  form.notes = ''
  hint.value = ''
}

watch(() => props.preset, (p) => {
  if (!p) return
  form.code = p.code || ''
  form.name = p.name || ''
  form.type = /^(sh5|sz1)/.test(form.code) ? 'etf' : 'stock'
  form.keyword = form.name ? `${form.name}  ${String(form.code).replace(/^(sh|sz)/i, '')}` : form.code
  form.rating = 'auto'
  form.notes = ''
  peekQuote()
}, { immediate: true })

watch(() => props.modelValue, (v) => {
  if (v && !props.preset) reset()
})

async function save() {
  if (!form.code) await peekQuote()
  if (!form.code) {
    ElMessage.warning('请输入股票名称或代码')
    return
  }
  saving.value = true
  try {
    const analysis = {
      code: form.code,
      name: form.name || form.code,
      type: form.type,
      notes: form.notes || '',
      ratingManual: form.rating === 'auto' ? null : form.rating,
      rating: form.rating === 'auto' ? null : form.rating,
    }
    await dash.addStock({ code: form.code, analysis })
    ElMessage.success('已添加标的')
    close()
  } catch (e) {
    ElMessage.error('添加失败：' + (e.message || e))
  } finally {
    saving.value = false
  }
}
</script>
