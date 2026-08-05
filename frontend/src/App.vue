<template>
  <LoginPage v-if="!auth.isAuthed" @login="onLogin" />
  <div v-else :class="['app-root', `theme-${theme}`]">
    <header class="header">
      <div class="header-inner">
        <div class="header-left">
          <div class="brand">Jarvis · 交易参谋</div>
          <span :class="['dot', stale ? 'stale' : '']"></span>
          <div class="sub">
            {{ dash.lastUpdate ? ('行情 ' + formatTime(dash.lastUpdate)) : '等待行情…' }}
            · LLM {{ dash.health?.llmConfigured ? '已配置' : '未配置' }}
          </div>
        </div>
        <div class="header-actions">
          <span class="user-chip" :title="auth.account">
            {{ auth.displayName || auth.account || '未登录' }}
            <em v-if="auth.roleLabel">{{ auth.roleLabel }}</em>
          </span>
          <button class="btn theme-btn" :title="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'" @click="toggleTheme">
            <span class="theme-icon">👕</span>{{ theme === 'dark' ? '浅色' : '深色' }}
          </button>
          <button class="btn" @click="onLogout">退出登录</button>
          <button class="btn" :disabled="dash.loading" @click="dash.refresh()">刷新</button>
          <button class="btn" @click="openPosition()">持仓管理</button>
          <button class="btn btn-primary" @click="openAdd()">+ 添加标的</button>
          <button class="btn" @click="dash.strategyOpen = true">策略引擎</button>
          <button class="btn btn-primary" @click="dash.chatOpen = true">Jarvis 对话</button>
        </div>
      </div>
    </header>

    <AlertBanner :alerts="dash.alerts" @journal="onJournal" />

    <main class="page-shell">
      <div class="app-shell">
        <aside class="sidebar">
          <div class="nav-group">
            <div class="nav-group-title"><span>标的分析</span></div>
            <div class="nav-items">
              <button
                v-for="v in views"
                :key="v.id"
                :class="['nav-item', { active: dash.view === v.id }]"
                @click="dash.view = v.id"
              >{{ v.label }}</button>
            </div>
          </div>
          <div class="nav-group">
            <div class="nav-group-title"><span>策略 / 工具</span></div>
            <div class="nav-items">
              <button class="nav-item" @click="dash.strategyOpen = true">策略引擎</button>
              <button class="nav-item" @click="openPosition()">持仓管理</button>
              <button class="nav-item" @click="openAdd()">添加标的</button>
              <button
                v-if="auth.can('kb.manage')"
                :class="['nav-item', { active: dash.view === 'knowledge' }]"
                @click="dash.view = 'knowledge'"
              >知识库</button>
              <button class="nav-item" @click="dash.chatOpen = true">Jarvis 对话</button>
            </div>
          </div>
        </aside>

        <div class="main-content">
          <div v-if="dash.error" class="error-banner">{{ dash.error }}</div>

          <MarketOverview
            v-if="dash.view !== 'knowledge'"
            :indices="dash.indices"
            :market-breadth="dash.marketBreadth"
            :overseas="dash.overseas"
            :conditions="dash.conditions"
            :lamps="dash.lamps"
            :position-rec="dash.positionRec"
            @toggle-lever="onToggleLever"
          />

          <div
            v-if="dash.view !== 'sectorFlow' && dash.view !== 'knowledge'"
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

          <template v-if="dash.view === 'stocks'">
            <MainRiseBar :main-rise="dash.mainRise" @toggle-ice="onToggleIce" />

            <FilterBar
              v-model:search="dash.search"
              v-model:filter="dash.filter"
              v-model:sector="dash.sector"
              :counts="dash.tabCounts"
              :sectors="dash.sectors"
            />

            <div class="section-head">
              <div class="section-head-left">
                <h2>{{ stockLayout === 'list' ? '标的列表' : '标的卡片' }}</h2>
                <span class="muted">共 {{ dash.cards.length }} / {{ dash.items.length }} 只</span>
              </div>
              <div class="layout-toggle" role="group" aria-label="标的展示形式">
                <button
                  type="button"
                  :class="{ active: stockLayout === 'card' }"
                  @click="setStockLayout('card')"
                >卡片</button>
                <button
                  type="button"
                  :class="{ active: stockLayout === 'list' }"
                  @click="setStockLayout('list')"
                >列表</button>
              </div>
            </div>

            <template v-if="dash.cards.length">
              <div v-if="stockLayout === 'card'" class="stock-grid">
                <StockCard
                  v-for="(c, idx) in dash.cards"
                  :key="c.code"
                  :card="c"
                  :idx="idx"
                  @review="onReview"
                  @edit-position="openPosition"
                  @journal="onJournal"
                />
              </div>
              <StockList
                v-else
                :cards="dash.cards"
                @review="onReview"
                @edit-position="openPosition"
                @journal="onJournal"
              />
            </template>
            <div v-else class="empty">没有匹配的标的。调整筛选，或点「添加标的」。</div>
          </template>

          <template v-else-if="dash.view === 'sectorFlow'">
            <SectorFlowBoard :data="dash.sectorFlow" />
          </template>

          <ScreenPanel
            v-else-if="dash.view === 'screen'"
            :rows="dash.screenResults"
            :meta="dash.screenMeta"
            :loading="dash.screenLoading"
            @refresh="dash.fetchScreen()"
            @add="openAdd"
          />

          <KnowledgePanel v-else-if="dash.view === 'knowledge'" />

          <AuctionPanel
            v-else
            :rows="dash.auctionResults"
            :meta="dash.auctionMeta"
            :loading="dash.auctionLoading"
            @refresh="dash.fetchAuction()"
            @add="openAdd"
          />
        </div>
      </div>
    </main>

    <template v-if="dash.chatOpen">
      <div class="chat-backdrop" @click="dash.chatOpen = false" />
      <ChatPanel @close="dash.chatOpen = false" />
    </template>

    <PositionDialog v-model="dash.positionOpen" :preset="positionPreset" />
    <AddStockDialog v-model="dash.addOpen" :preset="addPreset" />
    <StrategyDrawer v-model="dash.strategyOpen" :journal="dash.journal" />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useDashboardStore } from './stores/dashboard'
import { useAuthStore } from './stores/auth'
import AlertBanner from './components/AlertBanner.vue'
import MarketOverview from './components/MarketOverview.vue'
import FilterBar from './components/FilterBar.vue'
import StockCard from './components/StockCard.vue'
import StockList from './components/StockList.vue'
import ChatPanel from './components/ChatPanel.vue'
import PositionDialog from './components/PositionDialog.vue'
import StrategyDrawer from './components/StrategyDrawer.vue'
import MainRiseBar from './components/MainRiseBar.vue'
import ScreenPanel from './components/ScreenPanel.vue'
import AuctionPanel from './components/AuctionPanel.vue'
import AddStockDialog from './components/AddStockDialog.vue'
import LoginPage from './components/LoginPage.vue'
import SectorFlowBoard from './components/SectorFlowBoard.vue'
import KnowledgePanel from './components/KnowledgePanel.vue'

const dash = useDashboardStore()
const auth = useAuthStore()
const positionPreset = ref(null)
const addPreset = ref(null)
const THEME_KEY = 'jarvis-theme'
const LAYOUT_KEY = 'jarvis-stock-layout'
const theme = ref(localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark')
const stockLayout = ref(localStorage.getItem(LAYOUT_KEY) === 'list' ? 'list' : 'card')
let timer = null

const views = [
  { id: 'stocks', label: '自选标的' },
  { id: 'sectorFlow', label: '板块资金流向' },
  { id: 'screen', label: '盘后选股池' },
  { id: 'auction', label: '竞价异动榜' },
]

const stale = computed(() => {
  if (!dash.lastUpdate) return true
  return Date.now() - new Date(dash.lastUpdate).getTime() > 30000
})
const sectorFlowTop = computed(() => (dash.sectorFlow?.list || [])[0] || null)
const sectorFlowBottom = computed(() => {
  const list = dash.sectorFlow?.list || []
  if (!list.length) return null
  return [...list].sort((a, b) => a.netInflow - b.netInflow)[0] || null
})

function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString('zh-CN') } catch { return iso }
}

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  localStorage.setItem(THEME_KEY, theme.value)
  applyTheme(theme.value)
}

function setStockLayout(next) {
  stockLayout.value = next === 'list' ? 'list' : 'card'
  localStorage.setItem(LAYOUT_KEY, stockLayout.value)
}

function applyTheme(nextTheme) {
  document.documentElement.setAttribute('data-theme', nextTheme)
  document.body.setAttribute('data-theme', nextTheme)
}

function openPosition(card = null) {
  positionPreset.value = card
  dash.positionOpen = true
}

function openAdd(row = null) {
  addPreset.value = row
  dash.addOpen = true
}

async function onReview(code, riskOk) {
  try {
    const { value } = await ElMessageBox.prompt('复核备注（可空）', riskOk ? '利空通过' : '利空未过', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: dash.analyses[code]?.notes || '',
      inputPlaceholder: '可选备注',
    })
    await dash.reviewAnalysis(code, riskOk, value)
    ElMessage.success('已更新利空复核')
  } catch { /* cancel */ }
}

async function onJournal(alert) {
  try {
    const { value } = await ElMessageBox.prompt('日记备注（可空）', '记入纪律日记', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputPlaceholder: '实际执行了什么',
    })
    await dash.journalAlert(alert, value || '')
    ElMessage.success('已记入日记')
  } catch { /* cancel */ }
}

function onToggleLever() {
  dash.flipLever()
  ElMessage.info('已切换「杠杆5连降」手动标记')
}

function onToggleIce() {
  dash.flipIce()
  ElMessage.info('已切换「昨日冰点」手动确认')
}

async function onLogin({ account, password }) {
  const result = await auth.login(account, password)
  if (result.ok) {
    ElMessage.success('登录成功')
    return
  }
  ElMessage.error(result.error || '登录失败')
}

async function onLogout() {
  await auth.logout()
  dash.chatOpen = false
}

watch(() => dash.view, (v) => {
  if (v === 'screen' && !dash.screenResults.length) dash.fetchScreen()
  if (v === 'auction' && !dash.auctionResults.length) dash.fetchAuction()
})

watch(() => auth.isAuthed, async (authed) => {
  if (!authed) {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    return
  }
  await dash.refresh()
  if (!timer) timer = setInterval(() => dash.refresh(), 10000)
})

onMounted(async () => {
  applyTheme(theme.value)
  await auth.restore()
  if (!auth.isAuthed) return
  dash.chatOpen = false
  await dash.refresh()
  timer = setInterval(() => dash.refresh(), 10000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>
