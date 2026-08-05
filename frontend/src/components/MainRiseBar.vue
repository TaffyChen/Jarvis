<template>
  <div class="mainrise-bar" @click="expanded = !expanded">
    <div class="mainrise-mini">
      <span class="mainrise-title">主升第一天</span>
      <span :class="['mainrise-summary', mainRise.cls]">{{ mainRise.summary }}</span>
      <span class="mainrise-count">{{ mainRise.met }}/{{ mainRise.total }}</span>
      <button class="btn btn-sm btn-ghost" @click.stop="expanded = !expanded">
        {{ expanded ? '收起' : '展开' }}
      </button>
    </div>
    <div v-if="expanded" class="mainrise-checks" @click.stop>
      <div
        v-for="c in mainRise.checks"
        :key="c.name"
        :class="['mainrise-check', c.unknown ? 'unknown' : (c.met ? 'met' : 'unmet'), { manual: c.manual }]"
        @click="c.manual && $emit('toggle-ice')"
      >
        <span class="icon">{{ c.unknown ? '?' : (c.met ? '✓' : '✗') }}</span>
        <div>
          <div class="name">{{ c.name }}{{ c.manual ? '（点此切换）' : '' }}</div>
          <div class="detail">{{ c.detail }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
defineProps({
  mainRise: { type: Object, required: true },
})
defineEmits(['toggle-ice'])
const expanded = ref(false)
</script>
