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
      <h4>五灯仓位</h4>
      <p class="rule">换手拥挤 / 杠杆5连降 / 业绩验证期 / 海外隔夜大跌 / 持仓破20日线过半</p>
      <p class="rule">0红8成 · 1红5成 · 2红3成 · 3红1成 · 4-5红归零</p>
      <p class="rule warn">有效仓位 = min(五灯上限, 情绪退潮3成)</p>
      <p class="rule warn">海外阈值：标普日跌≤-1.5% 或 纳指ETF≤-2%</p>
    </div>
  </el-drawer>
</template>

<script setup>
defineProps({
  modelValue: Boolean,
})
defineEmits(['update:modelValue'])
</script>
