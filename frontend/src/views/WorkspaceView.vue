<template>
  <MarketOverview
    v-if="dash.view !== 'knowledge' && dash.view !== 'journal' && dash.view !== 'review'"
    :indices="dash.indices"
    :market-breadth="dash.marketBreadth"
    :overseas="dash.overseas"
    :conditions="dash.conditions"
    :lamps="dash.lamps"
    :position-rec="dash.positionRec"
    @toggle-lever="$emit('toggle-lever')"
  />

  <div
    v-if="dash.view !== 'sectorFlow' && dash.view !== 'knowledge' && dash.view !== 'journal' && dash.view !== 'review'"
    class="mainrise-bar"
    role="button"
    tabindex="0"
    @click="dash.view = 'sectorFlow'"
  >
    <div class="mainrise-mini">
      <div class="mainrise-title">板块资金流摘要</div>
      <div class="mainrise-summary" :class="sectorFlowTop?.netInflow > 0 ? 'met' : 'unmet'">
        流入 Top1：{{ sectorFlowTop?.sectorName || '--' }}
        {{ sectorFlowTop ? `${sectorFlowTop.netInflow > 0 ? '+' : ''}${sectorFlowTop.netInflow.toFixed(1)}亿` : '' }}
        · 流出 Top1：{{ sectorFlowBottom?.sectorName || '--' }}
        {{ sectorFlowBottom ? `${sectorFlowBottom.netInflow.toFixed(1)}亿` : '' }}
      </div>
      <span class="mainrise-count">查看双向榜</span>
    </div>
  </div>

  <StocksView
    v-if="dash.view === 'stocks'"
    :stock-layout="stockLayout"
    @toggle-ice="$emit('toggle-ice')"
    @layout="(v) => $emit('layout', v)"
    @review="(code, ok) => $emit('review', code, ok)"
    @edit-position="(card) => $emit('edit-position', card)"
    @journal="(a) => $emit('journal', a)"
  />
  <SectorFlowBoard v-else-if="dash.view === 'sectorFlow'" :data="dash.sectorFlow" />
  <ScreenPanel
    v-else-if="dash.view === 'screen'"
    :rows="dash.screenResults"
    :meta="dash.screenMeta"
    :loading="dash.screenLoading"
    @refresh="dash.fetchScreen()"
    @add="(row) => $emit('add', row)"
  />
  <KnowledgePanel v-else-if="dash.view === 'knowledge'" />
  <JournalPanel v-else-if="dash.view === 'journal'" />
  <ReviewPanel v-else-if="dash.view === 'review'" />
  <AuctionPanel
    v-else
    :rows="dash.auctionResults"
    :meta="dash.auctionMeta"
    :loading="dash.auctionLoading"
    @refresh="dash.fetchAuction()"
    @add="(row) => $emit('add', row)"
  />
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import MarketOverview from '../components/MarketOverview.vue'
import SectorFlowBoard from '../components/SectorFlowBoard.vue'
import ScreenPanel from '../components/ScreenPanel.vue'
import AuctionPanel from '../components/AuctionPanel.vue'
import KnowledgePanel from '../components/KnowledgePanel.vue'
import JournalPanel from '../components/JournalPanel.vue'
import ReviewPanel from '../components/ReviewPanel.vue'
import StocksView from './StocksView.vue'

defineProps({
  stockLayout: { type: String, default: 'card' },
})
defineEmits(['toggle-lever', 'toggle-ice', 'layout', 'review', 'edit-position', 'journal', 'add'])

const dash = useDashboardStore()
const sectorFlowTop = computed(() => (dash.sectorFlow?.list || [])[0] || null)
const sectorFlowBottom = computed(() => {
  const list = dash.sectorFlow?.list || []
  if (!list.length) return null
  return [...list].sort((a, b) => a.netInflow - b.netInflow)[0] || null
})
</script>
