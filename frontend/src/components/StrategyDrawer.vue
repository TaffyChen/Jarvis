<template>
  <el-drawer :model-value="modelValue" title="策略引擎 · 交易纪律" size="480px" @close="$emit('update:modelValue', false)">
    <div class="strategy-block">
      <h4>评分与分类</h4>
      <p class="rule">综合分 = PE(25)+趋势(25)+20日动量(20)+量比(15)+委比(15)</p>
      <p class="rule">可买入：≥60 且利空复核有效（≤14天）</p>
      <p class="rule warn">评分够但未复核/过期 → 最高只能观察</p>
    </div>
    <div class="strategy-block">
      <h4>灵魂三问</h4>
      <p class="rule">① 在20日线上吗？量能放大了吗？</p>
      <p class="rule">② 如果现在空仓，还会买它吗？</p>
      <p class="rule">③ 今天最高价回撤到止损线了吗？</p>
    </div>
    <div class="strategy-block">
      <h4>五条铁律</h4>
      <p class="rule danger">1. 破20日线减半仓，破60日线或次日未站回清仓</p>
      <p class="rule danger">2. 浮盈超10%后从高点回撤3%~5%离场</p>
      <p class="rule danger">3. 浮盈翻绿保本出局</p>
      <p class="rule warn">4. 情绪退潮只卖不买，仓位≤3成；与五灯并存时取更严</p>
      <p class="rule danger">5. 高位巨量长阴线清仓</p>
    </div>
    <div class="strategy-block">
      <h4>五灯仓位（全市场 v2.1）</h4>
      <p class="rule">硬灯：指数破位(1–2) / 海外冲击 / 生态恶化（破板·高潮·大回撤）</p>
      <p class="rule">软灯：业绩窗口 / 杠杆退潮(手动) — 单独不能归零</p>
      <p class="rule">风险分→仓位：0→8成 · ≤1→5成 · ≤2→3成 · ≤3→1成 · ≥3.5→归零</p>
      <p class="rule warn">不用自选/持仓样本；持仓破线走预警与铁律</p>
      <p class="rule warn">有效仓位 = min(五灯加权上限, 情绪退潮3成)</p>
    </div>
  </el-drawer>
</template>

<script setup>
defineProps({
  modelValue: Boolean,
})
defineEmits(['update:modelValue'])
</script>
