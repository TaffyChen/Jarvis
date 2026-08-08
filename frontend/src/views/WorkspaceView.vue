<template>
  <MarketView
    v-if="dash.view === 'market'"
    @toggle-lever="$emit('toggle-lever')"
    @toggle-ice="$emit('toggle-ice')"
    @open-sector="dash.view = 'sectorFlow'"
    @open-stocks="dash.view = 'stocks'"
  />

  <StocksView
    v-else-if="dash.view === 'stocks'"
    :stock-layout="stockLayout"
    @layout="(v) => $emit('layout', v)"
    @review="(code, ok) => $emit('review', code, ok)"
    @edit-position="(card) => $emit('edit-position', card)"
    @journal="(a) => $emit('journal', a)"
    @remove="(card) => $emit('remove', card)"
    @open-market="dash.view = 'market'"
  />
  <SectorFlowBoard
    v-else-if="dash.view === 'sectorFlow'"
    :data="dash.sectorFlow"
    :items="dash.items"
    :quotes="dash.quotes"
    :positions="dash.positions"
  />
  <ScreenPanel
    v-else-if="dash.view === 'screen'"
    :rows="dash.screenResults"
    :trend-rows="dash.screenTrendResults"
    :meta="dash.screenMeta"
    :loading="dash.screenLoading"
    @refresh="dash.fetchScreen()"
    @add="(row) => $emit('add', row)"
  />
  <KnowledgePanel v-else-if="dash.view === 'knowledge'" />
  <JournalPanel v-else-if="dash.view === 'journal'" />
  <ReviewPanel v-else-if="dash.view === 'review'" />
  <AuctionPanel
    v-else-if="dash.view === 'auction'"
    :rows="dash.auctionResults"
    :meta="dash.auctionMeta"
    :loading="dash.auctionLoading"
    @refresh="dash.fetchAuction()"
    @add="(row) => $emit('add', row)"
  />
</template>

<script setup>
import { useDashboardStore } from '../stores/dashboard'
import MarketView from './MarketView.vue'
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
defineEmits(['toggle-lever', 'toggle-ice', 'layout', 'review', 'edit-position', 'journal', 'add', 'remove'])

const dash = useDashboardStore()
</script>
