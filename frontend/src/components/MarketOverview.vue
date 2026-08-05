<template>
  <div class="overview">
    <div class="overview-inner">
      <div class="market-bar">
        <div v-for="(name, code) in indexNames" :key="code" class="chip">
          <div class="label">{{ name }}</div>
          <div class="val">
            {{ fmt(indices[code]?.price) }}
            <span :class="chgClass(indices[code]?.changePct)" style="font-size:12px;font-weight:600;margin-left:4px">
              {{ fmtPct(indices[code]?.changePct) }}
            </span>
          </div>
        </div>
        <div class="chip">
          <div class="label">全市场</div>
          <div class="val">
            <span class="up">↑{{ marketBreadth.up || 0 }}</span>
            <span class="down" style="margin-left:6px">↓{{ marketBreadth.down || 0 }}</span>
          </div>
        </div>
        <div class="chip" v-if="overseas">
          <div class="label">标普500</div>
          <div class="val" :class="chgClass(overseas.changePct)">{{ fmtPct(overseas.changePct) }}</div>
        </div>
        <div
          v-for="c in conditions"
          :key="c.name"
          :class="['cond', c.met === true ? 'met' : c.met === false ? 'unmet' : 'unknown']"
        >
          {{ c.met === true ? '✓' : c.met === false ? '✗' : '?' }} {{ c.name }}
        </div>
      </div>

      <div class="signal-bar">
        <span class="signal-label">五灯信号：</span>
        <div
          v-for="l in lamps"
          :key="l.name"
          :class="['lamp', l.red ? 'red' : 'green']"
          :title="l.detail"
          :style="l.manual ? 'cursor:pointer' : ''"
          @click="l.manual && $emit('toggle-lever')"
        >
          <span class="ball"></span>{{ l.name }}
        </div>
        <div :class="['pos-rec', positionRec.level]">
          {{ positionRec.redCount }}红灯 | {{ positionRec.text }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  indices: { type: Object, default: () => ({}) },
  marketBreadth: { type: Object, default: () => ({}) },
  overseas: { type: Object, default: null },
  conditions: { type: Array, default: () => [] },
  lamps: { type: Array, default: () => [] },
  positionRec: { type: Object, default: () => ({ redCount: 0, text: '', level: 'safe' }) },
})
defineEmits(['toggle-lever'])

const indexNames = {
  sh000001: '上证',
  sz399001: '深成',
  sz399006: '创业',
  sh000688: '科创50',
  sh000300: '沪深300',
}
function fmt(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(2)
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
</script>
