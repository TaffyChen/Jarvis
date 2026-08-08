<template>
  <el-dialog
    :model-value="modelValue"
    title="持仓管理"
    width="720px"
    class="pos-dialog"
    align-center
    @close="$emit('update:modelValue', false)"
  >
    <div class="pos-table-block">
      <div class="pos-table-head">
        <span class="pos-table-title">当前持仓</span>
        <span class="muted">点行编辑</span>
      </div>
      <el-table
        :data="rows"
        size="small"
        empty-text="暂无持仓"
        style="width:100%"
        max-height="240"
        highlight-current-row
        :row-class-name="rowClassName"
        @row-click="onRowClick"
      >
        <el-table-column label="标的" min-width="128">
          <template #default="{ row }">
            <span class="pos-name">{{ row.name }}</span>
            <span class="muted pos-code">{{ row.rawCode }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="buyPrice" label="成本" width="78" align="right" />
        <el-table-column prop="shares" label="股数" width="64" align="right" />
        <el-table-column prop="price" label="现价" width="70" align="right" />
        <el-table-column prop="stopText" label="止损" width="70" align="right" />
        <el-table-column prop="takeText" label="止盈" width="70" align="right" />
        <el-table-column label="盈亏" width="118" align="right">
          <template #default="{ row }">
            <span :class="row.hasQuote ? (row.pnl >= 0 ? 'up' : 'down') : 'muted'">
              {{ row.pnlText }}
              <span class="pos-pnl-pct">{{ row.pnlPctText }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="" width="40" align="center">
          <template #default="{ row }">
            <button
              type="button"
              class="pos-icon-btn"
              title="删除持仓"
              @click.stop="remove(row)"
            >
              <el-icon :size="14"><Delete /></el-icon>
            </button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pos-form-block">
      <div class="pos-form-head">
        <span class="pos-table-title">{{ editingExisting ? '编辑' : '新增' }}</span>
        <button v-if="editingExisting" type="button" class="btn btn-sm btn-ghost" @click="reset">取消</button>
      </div>

      <el-form class="pos-form" label-position="top" size="small">
        <el-form-item v-if="!editingExisting" label="搜索标的">
          <el-autocomplete
            v-model="form.keyword"
            :fetch-suggestions="querySearch"
            value-key="label"
            placeholder="名称或代码，如 美的 / 000333"
            style="width:100%"
            clearable
            @select="onSelect"
            @keyup.enter="resolveKeyword"
          />
        </el-form-item>
        <div v-if="form.code" class="pos-selected muted">
          {{ editingExisting ? '编辑中' : '已选' }}：
          <b>{{ form.name || form.code }}</b>
          · {{ displayCode }}
          <span v-if="quoteHint"> · {{ quoteHint }}</span>
        </div>
        <div class="pos-fields">
          <el-form-item label="买入价" style="flex:1;margin-bottom:8px">
            <el-input-number v-model="form.buyPrice" :step="0.01" :precision="3" controls-position="right" style="width:100%" />
          </el-form-item>
          <el-form-item label="股数" style="flex:1;margin-bottom:8px">
            <el-input-number v-model="form.shares" :step="100" :min="1" controls-position="right" style="width:100%" />
          </el-form-item>
          <el-form-item label="止损（空=成本-8%）" style="flex:1;margin-bottom:8px">
            <el-input-number
              v-model="form.stopLossPrice"
              :step="0.01"
              :precision="3"
              :min="0"
              controls-position="right"
              style="width:100%"
            />
          </el-form-item>
          <el-form-item label="止盈（空=成本+10%）" style="flex:1;margin-bottom:8px">
            <el-input-number
              v-model="form.takeProfitPrice"
              :step="0.01"
              :precision="3"
              :min="0"
              controls-position="right"
              style="width:100%"
            />
          </el-form-item>
        </div>
        <div v-if="autoHint" class="muted pos-hint">{{ autoHint }}</div>
      </el-form>
    </div>

    <template #footer>
      <el-button size="small" @click="$emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" size="small" :loading="saving" @click="save">
        {{ editingExisting ? '保存' : '添加' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import { useDashboardStore } from '../stores/dashboard'
import { api } from '../api'
import { positionRiskLevels, boardStopPcts, maxHighSinceBuy, isStrongTrend } from '../utils/signals'

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
const editingExisting = computed(() => !!(form.code && dash.positions[form.code]))

const quoteHint = computed(() => {
  const q = dash.quotes[form.code]
  if (!q?.price) return ''
  return `现价 ${Number(q.price).toFixed(2)}`
})

const autoHint = computed(() => {
  const buy = Number(form.buyPrice) || 0
  if (!(buy > 0)) return ''
  const code = form.code
  const name = dash.items.find((i) => i.code === code)?.name || form.name || ''
  const { cost, trail, label } = boardStopPcts(code, name)
  const sl = (buy * (1 + cost / 100)).toFixed(3)
  const tp = (buy * 1.1).toFixed(3)
  return `默认参考（${label}）：成本止损 ${sl}（${cost}%）· 跟踪${trail}% · 止盈 ${tp}（+10% 起）。铁律仍优先。`
})

const rows = computed(() => Object.keys(dash.positions).map((code) => {
  const pos = dash.positions[code]
  const item = dash.items.find((i) => i.code === code)
  const q = dash.quotes[code]
  const k = dash.klines[code]
  const price = q?.price || 0
  const hasQuote = price > 0
  const pnl = hasQuote ? (price - pos.buyPrice) * pos.shares : 0
  const pnlPct = hasQuote && pos.buyPrice > 0 ? (price - pos.buyPrice) / pos.buyPrice * 100 : 0
  const name = item?.name || pos.name || code
  const levels = positionRiskLevels(pos, price, {
    code,
    name,
    maxHigh: maxHighSinceBuy(k, pos) || price,
    strongTrend: isStrongTrend(k),
  })
  return {
    code,
    rawCode: code.replace(/^(sh|sz)/i, ''),
    name,
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

function rowClassName({ row }) {
  return row.code === form.code ? 'pos-row-active' : ''
}

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

function onRowClick(row) {
  applyHit({ code: row.code, name: row.name })
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
    // 持仓一律确保进入观察池+行情，避免「持仓管理有、标的列表没有」
    await api.addCodes([form.code])
    if (!dash.analyses[form.code]) {
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
    // 保留当前编辑选中，方便连续微调；新增后清空搜索区
    if (!old) reset()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || e))
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除持仓「${row.name}」？不会下单，只清本地登记。`,
      '删除持仓',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  const next = { ...dash.positions }
  delete next[row.code]
  await dash.savePositions(next)
  if (form.code === row.code) reset()
  ElMessage.success('已删除持仓')
}
</script>

<style scoped>
.pos-table-block { margin-bottom: 10px; }
.pos-table-head,
.pos-form-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.pos-table-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--bright);
}
.pos-name {
  font-weight: 600;
  color: var(--bright);
  margin-right: 6px;
  white-space: nowrap;
}
.pos-code {
  font-size: 12px;
  white-space: nowrap;
}
.pos-pnl-pct {
  margin-left: 4px;
  opacity: 0.85;
  font-size: 12px;
}
.pos-form-block {
  padding-top: 10px;
  border-top: 1px solid var(--border);
}
.pos-selected {
  margin: 0 0 6px;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pos-selected b { color: var(--bright); font-weight: 600; }
.pos-fields { display: flex; gap: 8px; flex-wrap: wrap; }
.pos-hint { margin: 0; font-size: 11px; line-height: 1.35; }
.pos-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}
.pos-icon-btn:hover {
  color: var(--red);
  border-color: var(--border);
  background: var(--red-bg, rgba(248, 81, 73, 0.12));
}
:deep(.pos-row-active > td) {
  background: var(--blue-bg, rgba(88, 166, 255, 0.12)) !important;
}
:deep(.el-table__body tr) { cursor: pointer; }
:deep(.el-table .cell) {
  line-height: 1.3;
  white-space: nowrap;
}
:deep(.el-form-item__label) {
  margin-bottom: 2px !important;
  font-size: 12px;
  line-height: 1.2;
}
:deep(.el-dialog__body) {
  padding-top: 8px;
  padding-bottom: 4px;
}
</style>
