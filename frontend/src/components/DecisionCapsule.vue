<template>
  <button
    type="button"
    class="decision-capsule"
    :class="rec.level"
    :title="tip"
    @click="$emit('open-market')"
  >
    <span class="cap-item">
      <em>仓位</em>
      <strong>{{ capText }}</strong>
      <b :class="rec.buyAllowed === false ? 'no' : 'ok'">
        {{ rec.buyAllowed === false ? '禁开' : '可参' }}
      </b>
    </span>
    <span class="cap-sep" />
    <span class="cap-item">
      <em>情绪</em>
      <strong :class="cycleClass">{{ cycleLabel }}</strong>
      <b class="muted">{{ tempText }}</b>
    </span>
    <span class="cap-sep" />
    <span class="cap-item grow">
      <em>主线</em>
      <strong class="focus">{{ focusText }}</strong>
      <b class="muted">{{ styleText }}</b>
    </span>
    <span class="cap-link">盘面 ▸</span>
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  positionRec: { type: Object, default: () => ({}) },
  sentiment: { type: Object, default: () => ({}) },
  advice: { type: Object, default: () => ({}) },
})
defineEmits(['open-market'])

const rec = computed(() => props.positionRec || {})
const capText = computed(() => {
  const cap = rec.value.cap
  if (cap == null || !Number.isFinite(Number(cap))) return props.advice?.positionText || '--'
  if (cap <= 0) return '0%'
  return `≤${Math.round(cap * 100)}%`
})
const cycleLabel = computed(() => props.sentiment?.cycle?.label || props.sentiment?.phase || '--')
const cycleClass = computed(() => {
  const id = props.sentiment?.cycle?.id
  if (id === 'ice' || id === 'retreat') return 'cold'
  if (id === 'climax' || id === 'diverge') return 'hot'
  if (id === 'ferment') return 'warm'
  return props.sentiment?.phaseClass || ''
})
const tempText = computed(() => {
  const t = props.sentiment?.temp
  return t != null ? `${t}°` : ''
})
const focusText = computed(() => {
  const lines = props.advice?.focusLines || []
  if (lines.length) return lines[0].name
  return props.advice?.focusText || '待确认'
})
const styleText = computed(() => props.advice?.style || '')
const tip = computed(() => {
  const parts = [
    `仓位 ${capText.value}`,
    `情绪 ${cycleLabel.value}`,
    `主线 ${focusText.value}`,
    '点击打开盘面',
  ]
  return parts.join(' · ')
})
</script>

<style scoped>
.decision-capsule {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  margin: 0 0 6px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--card-bg);
  color: inherit;
  cursor: pointer;
  text-align: left;
  box-shadow: var(--shadow-sm);
  transition: border-color 0.15s ease;
}
.decision-capsule:hover {
  border-color: rgba(88, 166, 255, 0.45);
}
.decision-capsule.danger { background: linear-gradient(90deg, var(--red-bg), transparent 40%); }
.decision-capsule.warning { background: linear-gradient(90deg, var(--orange-bg), transparent 40%); }
.decision-capsule.safe { background: linear-gradient(90deg, var(--green-bg), transparent 40%); }

.cap-item {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  min-width: 0;
  white-space: nowrap;
}
.cap-item.grow {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.cap-item em {
  font-style: normal;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.04em;
}
.cap-item strong {
  font-size: 13px;
  color: var(--bright);
  font-variant-numeric: tabular-nums;
}
.cap-item strong.focus {
  overflow: hidden;
  text-overflow: ellipsis;
}
.cap-item strong.hot { color: var(--red); }
.cap-item strong.warm { color: var(--orange); }
.cap-item strong.cold { color: var(--green); }
.cap-item b {
  font-size: 11px;
  font-weight: 700;
}
.cap-item b.ok { color: var(--blue); }
.cap-item b.no { color: var(--red); }
.cap-item b.muted { color: var(--muted); font-weight: 500; }
.cap-sep {
  width: 1px;
  height: 14px;
  background: var(--border);
  flex-shrink: 0;
}
.cap-link {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: var(--blue);
  margin-left: auto;
}
@media (max-width: 720px) {
  .cap-sep,
  .cap-item b.muted { display: none; }
}
</style>
