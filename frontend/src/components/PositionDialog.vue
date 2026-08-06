<template>
  <el-dialog :model-value="modelValue" title="持仓管理" width="920px" @close="$emit('update:modelValue', false)">
    <div style="margin-bottom:14px">
      <div class="muted" style="margin-bottom:8px;font-weight:700;color:var(--bright)">当前持仓</div>
      <el-table :data="rows" size="small" empty-text="暂无持仓" style="width:100%">
        <el-table-column prop="name" label="标的" min-width="110" />
        <el-table-column prop="buyPrice" label="成本" width="88" />
        <el-table-column prop="shares" label="股数" width="72" />
        <el-table-column prop="price" label="现价" width="80" />
        <el-table-column prop="stopText" label="止损" width="88" />
        <el-table-column prop="takeText" label="止盈" width="88" />
        <el-table-column label="盈亏额" width="96">
          <template #default="{ row }">
            <span :class="row.hasQuote ? (row.pnl >= 0 ? 'up' : 'down') : 'muted'">{{ row.pnlText }}</span>
          </template>
        </el-table-column>
        <el-table-column label="盈亏比例" width="96">
          <template #default="{ row }">
            <span :class="row.hasQuote ? (row.pnlPct >= 0 ? 'up' : 'down') : 'muted'">{{ row.pnlPctText }}</span>
          </template>
        </el-table-column>
        <el-table-column label="" width="64">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row.code)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-form label-position="top">
      <el-form-item label="添加 / 修改持仓（输入名称或代码，不必先加入自选）">
        <el-autocomplete
          v-model="form.keyword"
          :fetch-suggestions="querySearch"
          value-key="label"
          placeholder="例如：美的 / 000333，回车或点选"
          style="width:100%"
          clearable
          @select="onSelect"
          @keyup.enter="resolveKeyword"
        />
      </el-form-item>
      <div v-if="form.code" class="muted" style="margin-top:-8px;margin-bottom:8px">
        已选：{{ form.name || form.code }} · {{ displayCode }}
        <span v-if="quoteHint"> · {{ quoteHint }}</span>
      </div>
      <div style="display:flex;gap:12px">
        <el-form-item label="买入价" style="flex:1">
          <el-input-number v-model="form.buyPrice" :step="0.01" :precision="3" style="width:100%" />
        </el-form-item>
        <el-form-item label="股数" style="flex:1">
          <el-input-number v-model="form.shares" :step="100" :min="1" style="width:100%" />
        </el-form-item>
      </div>
      <div style="display:flex;gap:12px">
        <el-form-item label="止损价（可选，空=成本-8%）" style="flex:1">
          <el-input-number
            v-model="form.stopLossPrice"
            :step="0.01"
            :precision="3"
            :min="0"
            controls-position="right"
            style="width:100%"
            placeholder="默认自动"
          />
        </el-form-item>
        <el-form-item label="止盈价（可选，空=成本+10%）" style="flex:1">
          <el-input-number
            v-model="form.takeProfitPrice"
            :step="0.01"
            :precision="3"
            :min="0"
            controls-position="right"
            style="width:100%"
            placeholder="默认自动"
          />
        </el-form-item>
      </div>
      <div v-if="autoHint" class="muted" style="margin-top:-6px;margin-bottom:8px;font-size:12px">
        {{ autoHint }}
      </div>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存持仓</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useDashboardStore } from '../stores/dashboard'
import { api } from '../api'
import { positionRiskLevels } from '../utils/signals'

const props = defineProps({
  modelValue: Boolean,
  preset: { type: Object, default: null },
})
defineEmits(['update:modelValue'])

const dash = useDashboardStore()
const saving = ref(false)
const form = reactive({
  keyword: '',
  code: '',
  name: '',
  buyPrice: 0,
  shares: 100,
  stopLossPrice: undefined,
  takeProfitPrice: undefined,
})

const displayCode = computed(() => String(form.code || '').replace(/^(sh|sz)/i, ''))

const quoteHint = computed(() => {
  const q = dash.quotes[form.code]
  if (!q?.price) return ''
  return `现价 ${Number(q.price).toFixed(2)}`
})

const autoHint = computed(() => {
  const buy = Number(form.buyPrice) || 0
  if (!(buy > 0)) return ''
  const sl = (buy * 0.92).toFixed(3)
  const tp = (buy * 1.1).toFixed(3)
  return `默认参考：止损 ${sl}（-8%）· 止盈 ${tp}（+10%）。铁律（破线/回撤）仍优先于价格。`
})

const rows = computed(() => Object.keys(dash.positions).map((code) => {
  const pos = dash.positions[code]
  const item = dash.items.find((i) => i.code === code)
  const q = dash.quotes[code]
  const price = q?.price || 0
  const hasQuote = price > 0
  const pnl = hasQuote ? (price - pos.buyPrice) * pos.shares : 0
  const pnlPct = hasQuote && pos.buyPrice > 0 ? (price - pos.buyPrice) / pos.buyPrice * 100 : 0
  const levels = positionRiskLevels(pos, price)
  return {
    code,
    name: item?.name || pos.name || code,
    buyPrice: Number(pos.buyPrice).toFixed(3),
    shares: pos.shares,
    price: hasQuote ? price.toFixed(2) : '--',
    hasQuote,
    pnl,
    pnlPct,
    pnlText: hasQuote ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(0)}` : '--',
    pnlPctText: hasQuote ? `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%` : '--',
    stopText: levels ? Number(levels.stopLoss).toFixed(2) : '--',
    takeText: levels ? Number(levels.takeProfit).toFixed(2) : '--',
  }
}))

function normalizeCode(raw) {
  const c = String(raw || '').trim().toLowerCase().replace(/^(sh|sz)/, '')
  if (!c) return ''
  if (!/^\d{5,6}$/.test(c)) return ''
  if (/^(5|6|9)/.test(c) || /^11|^12/.test(c)) return 'sh' + c
  return 'sz' + c
}

function reset() {
  form.keyword = ''
  form.code = ''
  form.name = ''
  form.buyPrice = 0
  form.shares = 100
  form.stopLossPrice = undefined
  form.takeProfitPrice = undefined
}

function applyHit(hit) {
  const code = hit.code || normalizeCode(hit.raw || form.keyword)
  if (!code) return
  form.code = code
  form.name = hit.name || dash.quotes[code]?.name || form.name
  form.keyword = form.name
    ? `${form.name}  ${code.replace(/^(sh|sz)/i, '')}`
    : code.replace(/^(sh|sz)/i, '')
  const pos = dash.positions[code]
  const q = dash.quotes[code]
  if (pos) {
    form.buyPrice = pos.buyPrice
    form.shares = pos.shares
    form.name = pos.name || form.name
    form.stopLossPrice = pos.stopLossPrice > 0 ? pos.stopLossPrice : undefined
    form.takeProfitPrice = pos.takeProfitPrice > 0 ? pos.takeProfitPrice : undefined
  } else if (q?.price && !(form.buyPrice > 0)) {
    form.buyPrice = q.price
    form.stopLossPrice = undefined
    form.takeProfitPrice = undefined
  }
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

function onSelect(item) {
  applyHit(item)
}

async function resolveKeyword() {
  if (form.code && form.keyword.includes(displayCode.value)) return
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
  const code = normalizeCode(q)
  if (code) applyHit({ code, name: dash.quotes[code]?.name || '' })
}

watch(() => props.preset, (p) => {
  if (!p) return
  applyHit({
    code: p.code,
    name: p.name || '',
  })
  if (p.pos?.buyPrice) form.buyPrice = p.pos.buyPrice
  if (p.pos?.shares) form.shares = p.pos.shares
  form.stopLossPrice = p.pos?.stopLossPrice > 0 ? p.pos.stopLossPrice : undefined
  form.takeProfitPrice = p.pos?.takeProfitPrice > 0 ? p.pos.takeProfitPrice : undefined
  if (!p.pos && p.q?.price && !(form.buyPrice > 0)) form.buyPrice = p.q.price
}, { immediate: true })

watch(() => props.modelValue, (v) => {
  if (v && !props.preset) reset()
})

async function save() {
  if (!form.code) await resolveKeyword()
  if (!form.code || !(form.buyPrice > 0) || !(form.shares > 0)) {
    ElMessage.warning('请选择标的并填写买入价、股数')
    return
  }
  saving.value = true
  try {
    const exists = dash.items.some((i) => i.code === form.code)
      || Object.prototype.hasOwnProperty.call(dash.quotes, form.code)
      || Object.prototype.hasOwnProperty.call(dash.analyses, form.code)
    if (!exists) {
      await api.addCodes([form.code])
      await api.upsertAnalysis({
        code: form.code,
        name: form.name || form.code,
      })
    }
    const next = { ...dash.positions }
    const old = next[form.code]
    const row = {
      buyPrice: form.buyPrice,
      shares: form.shares,
      name: form.name || old?.name,
      date: old?.date || new Date().toISOString().slice(0, 10),
    }
    if (form.stopLossPrice > 0) row.stopLossPrice = Number(form.stopLossPrice)
    if (form.takeProfitPrice > 0) row.takeProfitPrice = Number(form.takeProfitPrice)
    next[form.code] = row
    await dash.savePositions(next)
    ElMessage.success(`已保存 ${form.name || form.code}`)
    reset()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || e))
  } finally {
    saving.value = false
  }
}

async function remove(code) {
  const next = { ...dash.positions }
  delete next[code]
  await dash.savePositions(next)
  ElMessage.success('已删除')
}
</script>
