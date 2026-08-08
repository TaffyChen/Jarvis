<template>
  <div :class="['overview', { 'page-mode': pageMode }]">
    <div class="overview-inner">
      <div class="market-bar">
        <div
          class="turn-card"
          :class="turnoverTone"
          :title="turnoverTip"
        >
          <div class="row1">
            <span class="name">三市</span>
            <span class="amt">{{ turnoverAmountText }}</span>
          </div>
          <div class="row2">
            <span class="sub">较上日此时</span>
            <span class="delta">{{ turnoverDeltaText }}</span>
          </div>
        </div>
        <div
          v-for="(name, code) in indexNames"
          :key="code"
          class="idx-card"
          :class="indexVol(code).state"
          :title="indexVol(code).tip"
        >
          <div class="row1">
            <span class="name">{{ name }}</span>
            <span class="price">{{ fmt(indices[code]?.price) }}</span>
            <span :class="['chg', chgClass(indices[code]?.changePct)]">
              {{ fmtPct(indices[code]?.changePct) }}
            </span>
          </div>
          <div class="row2" :class="indexVol(code).state">
            <span class="tag">{{ indexVol(code).tag }}</span>
            <span class="lb">{{ indexVol(code).liangbiText }}</span>
            <span class="amt">{{ indexVol(code).amountText }}</span>
          </div>
        </div>
        <div class="ov-card" v-if="overseas && overseas.changePct != null">
          <span class="name">标普</span>
          <span :class="['chg', chgClass(overseas.changePct)]">{{ fmtPct(overseas.changePct) }}</span>
        </div>
        <div class="ov-card" v-if="overseas?.nasdaq?.changePct != null">
          <span class="name">纳指</span>
          <span :class="['chg', chgClass(overseas.nasdaq.changePct)]">{{ fmtPct(overseas.nasdaq.changePct) }}</span>
        </div>
        <div class="ov-card" v-if="overseas?.nikkei?.changePct != null">
          <span class="name">日经</span>
          <span :class="['chg', chgClass(overseas.nikkei.changePct)]">{{ fmtPct(overseas.nikkei.changePct) }}</span>
        </div>
        <div class="ov-card" v-if="overseas?.kospi?.changePct != null">
          <span class="name">韩国</span>
          <span :class="['chg', chgClass(overseas.kospi.changePct)]">{{ fmtPct(overseas.kospi.changePct) }}</span>
        </div>
      </div>

      <!-- 决策摘要：盘面页常显；其他场景可点开细节 -->
      <div
        class="cmd-strip"
        :class="{ open: showDetail, static: pageMode }"
        :role="pageMode ? undefined : 'button'"
        :tabindex="pageMode ? undefined : 0"
        :aria-expanded="pageMode ? undefined : showDetail"
        @click="!pageMode && (expanded = !expanded)"
        @keydown.enter.prevent="!pageMode && (expanded = !expanded)"
        @keydown.space.prevent="!pageMode && (expanded = !expanded)"
      >
        <div class="cmd-seg cap" :class="positionRec.level" :title="positionRec.detail || positionRec.text">
          <span class="seg-label">仓位</span>
          <div class="seg-main">
            <strong>{{ capText }}</strong>
            <span :class="['seg-flag', positionRec.buyAllowed === false ? 'no' : 'ok']">
              {{ positionRec.buyAllowed === false ? '禁开' : '可参' }}
            </span>
          </div>
          <div class="lamp-dots" :title="`风险分 ${positionRec.riskScore ?? 0}`" @click.stop>
            <i
              v-for="l in lamps"
              :key="l.id || l.name"
              :class="['dot', l.red ? 'on' : '', l.kind === 'soft' ? 'soft' : 'hard', l.manual ? 'manual' : '']"
              :title="`${l.name}${l.red ? '·亮' : '·灭'} ${l.detail || ''}`"
              @click="l.manual && $emit('toggle-lever')"
            />
          </div>
        </div>

        <div class="cmd-seg mood" :title="cycleTip || sentiment.formula">
          <span class="seg-label">情绪</span>
          <div class="mood-row">
            <div class="temp-gauge mini" :class="sentiment.phaseClass">
              <svg viewBox="0 0 80 52" class="gauge-svg" aria-hidden="true">
                <path
                  class="gauge-track"
                  pathLength="100"
                  d="M 10 42 A 30 30 0 0 0 70 42"
                />
                <path
                  class="gauge-fill"
                  pathLength="100"
                  d="M 10 42 A 30 30 0 0 0 70 42"
                  :style="{ strokeDasharray: `${tempArc} 100` }"
                />
              </svg>
              <div class="gauge-readout">
                <b>{{ sentiment.temp ?? '--' }}</b>
              </div>
            </div>
            <div class="mood-text-col">
              <span :class="['phase-text', cycleClass || sentiment.phaseClass]">
                {{ cycleLabel || sentiment.phase }}
              </span>
              <span class="phase-sub">{{ sentiment.temp ?? '--' }}°</span>
            </div>
          </div>
        </div>

        <div class="cmd-seg focus" @click.stop="$emit('open-sector')">
          <span class="seg-label">主线</span>
          <div class="seg-main">
            <strong class="focus-name">{{ primaryFocus }}</strong>
            <span v-if="primaryAccel" :class="['accel-tag', primaryAccel]">{{ primaryAccelLabel }}</span>
          </div>
          <div class="seg-sub" :title="sectorFlowTip">
            <span>{{ advice.style || '观察为主' }}</span>
            <span v-if="sectorFlowBrief" class="flow-brief">· {{ sectorFlowBrief }}</span>
          </div>
        </div>

        <div class="cmd-seg map">
          <span class="seg-label">自选</span>
          <div class="seg-main">
            <strong v-if="advice.readyCount">{{ advice.readyCount }} 可考虑</strong>
            <strong v-else-if="advice.watchHitCount">{{ advice.watchHitCount }} 重合</strong>
            <strong v-else class="muted-strong">暂无重合</strong>
          </div>
          <div class="seg-sub">{{ mapHint }}</div>
        </div>

        <div
          v-if="!pageMode"
          class="cmd-chevron"
          :aria-label="expanded ? '收起' : '展开细节'"
        >
          <span>{{ expanded ? '收起' : '细节' }}</span>
          <em :class="{ open: expanded }">▾</em>
        </div>
      </div>

      <div v-if="showDetail" class="cmd-detail">
        <div class="detail-lamps">
          <div class="detail-lamps-head">
            <div class="detail-title">五灯</div>
            <div class="lamp-cap" :class="positionRec.level">
              <strong>{{ capText }}</strong>
              <span>{{ positionRec.buyAllowed === false ? '禁开仓' : '可参与' }}</span>
              <em v-if="positionRec.riskScore != null">风险{{ positionRec.riskScore }}</em>
            </div>
          </div>
          <div class="lamp-row">
            <div
              v-for="l in lamps"
              :key="l.id || l.name"
              :class="['lamp', l.red ? 'red' : 'green', l.kind === 'soft' ? 'soft' : '']"
              :title="l.detail"
              :style="l.manual ? 'cursor:pointer' : ''"
              @click="l.manual && $emit('toggle-lever')"
            >
              <div class="lamp-top">
                <span class="ball"></span>
                <span class="lamp-name">{{ l.name }}</span>
                <small v-if="l.red">×{{ l.weight }}</small>
              </div>
              <span v-if="l.detail" class="lamp-why">{{ lampWhy(l) }}</span>
            </div>
          </div>
          <div v-if="positionRec.text" class="muted detail-note">{{ positionRec.text }}</div>
        </div>

        <div class="detail-main">
          <div class="detail-col mood-col">
            <div class="detail-title">市场情绪</div>
            <div
              v-if="cycleSteps.length"
              class="cycle-track"
              :title="cycleTip"
            >
              <div
                v-for="(s, i) in cycleSteps"
                :key="s.id"
                :class="['cycle-step', s.id, { active: i === cycleIndex, passed: i < cycleIndex }]"
              >
                <i />
                <span>{{ s.label }}</span>
              </div>
            </div>
            <p v-if="cycleReason && !pageMode" class="cycle-reason muted">{{ cycleReason }}</p>
            <div class="mood-detail-head">
              <div class="mood-now" :title="sentiment.formula">
                <div class="mood-now-temp" :class="sentiment.phaseClass">
                  <b>{{ sentiment.temp ?? '--' }}</b>
                  <span class="mood-unit">°</span>
                  <span class="mood-phase">{{ cycleLabel || sentiment.phase || '—' }}</span>
                </div>
                <div class="mood-band-hint muted">
                  冰点 ≤{{ spark.iceBand }} · 沸点 ≥{{ spark.boilBand }}
                  <em v-if="tempVsBand">· {{ tempVsBand }}</em>
                </div>
                <div class="breadth-stats stacked">
                  <span><b class="up">↑{{ sentiment.up || 0 }}</b></span>
                  <span><b class="down">↓{{ sentiment.down || 0 }}</b></span>
                  <span>涨停 {{ sentiment.zt || 0 }} / 跌停 {{ sentiment.dt || 0 }}</span>
                  <span v-if="sentiment.upPct != null">上涨 {{ sentiment.upPct }}%</span>
                  <span v-if="heightSpark.now != null">最高板 {{ heightSpark.now }}</span>
                </div>
              </div>
              <div class="mood-charts">
                <div class="mood-spark-wrap" :title="sentimentHistory.note || '近一月情绪温度'">
                  <div class="spark-title">情绪温度</div>
                  <svg
                    v-if="spark.points.length >= 1"
                    class="mood-spark"
                    viewBox="0 0 240 78"
                    preserveAspectRatio="none"
                    aria-label="近一月情绪温度折线"
                  >
                    <rect
                      class="ice-band"
                      :x="0"
                      :y="spark.yAt(spark.iceBand)"
                      width="240"
                      :height="78 - spark.yAt(spark.iceBand)"
                    />
                    <rect
                      class="boil-band"
                      :x="0"
                      y="0"
                      width="240"
                      :height="spark.yAt(spark.boilBand)"
                    />
                    <line class="ice-line" x1="0" :y1="spark.yAt(spark.iceBand)" x2="240" :y2="spark.yAt(spark.iceBand)" />
                    <line class="boil-line" x1="0" :y1="spark.yAt(spark.boilBand)" x2="240" :y2="spark.yAt(spark.boilBand)" />
                    <text class="band-label ice" x="4" :y="Math.min(74, spark.yAt(spark.iceBand) + 10)">冰点 {{ spark.iceBand }}</text>
                    <text class="band-label boil" x="4" :y="Math.max(10, spark.yAt(spark.boilBand) - 3)">沸点 {{ spark.boilBand }}</text>
                    <polyline class="spark-line" :points="spark.poly" fill="none" />
                    <circle
                      v-if="spark.last"
                      class="spark-dot"
                      :class="[sentiment.phaseClass, spark.last.live ? 'live' : '']"
                      :cx="spark.last.x"
                      :cy="spark.last.y"
                      r="3.2"
                    />
                  </svg>
                  <div v-else class="mood-spark-empty muted">累计采样中…约一月交易日后更完整</div>
                  <div class="spark-meta">
                    <span>{{ spark.rangeLabel }} · 双阈值</span>
                    <span v-if="spark.firstT">{{ spark.firstT }}→{{ spark.lastT }}{{ spark.last?.live ? '·实时' : '' }}</span>
                  </div>
                </div>

                <div class="mood-spark-wrap height-wrap" title="近一月连板市场高度（最高板）">
                  <div class="spark-title">市场高度 · 最高板 {{ heightSpark.now ?? '--' }}</div>
                  <svg
                    v-if="heightSpark.points.length >= 1"
                    class="mood-spark height-spark"
                    viewBox="0 0 240 56"
                    preserveAspectRatio="none"
                    aria-label="近一月最高板"
                  >
                    <polyline class="spark-line height" :points="heightSpark.poly" fill="none" />
                    <circle
                      v-if="heightSpark.last"
                      class="spark-dot"
                      :class="heightSpark.last.live ? 'live warm' : 'warm'"
                      :cx="heightSpark.last.x"
                      :cy="heightSpark.last.y"
                      r="2.8"
                    />
                  </svg>
                  <div v-else class="mood-spark-empty muted short">开市后随情绪一并沉淀最高板</div>
                  <div class="spark-meta">
                    <span>连板高度</span>
                    <span v-if="heightSpark.firstT">{{ heightSpark.firstT }}→{{ heightSpark.lastT }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="effect-grid">
              <div
                v-for="e in sentiment.effects || []"
                :key="e.key"
                :class="['effect-chip', e.tone]"
                :title="e.tip"
              >
                <span>{{ e.label }}</span>
                <strong>{{ e.value }}</strong>
              </div>
            </div>
            <div class="ladder-row">
              <div v-for="step in sentiment.ladder || []" :key="step.key" class="ladder-chip">
                <span>{{ step.label }}</span><b>{{ step.count }}</b>
              </div>
            </div>
            <div class="cond-row">
              <span
                v-for="c in sentiment.conditions || conditions"
                :key="c.name"
                :class="['cond', c.met === true ? 'met' : c.met === false ? 'unmet' : 'unknown']"
                :title="c.detail || ''"
              >
                {{ c.met === true ? '✓' : c.met === false ? '✗' : '?' }} {{ c.name }}
              </span>
            </div>
          </div>

          <div class="detail-col advice-col">
            <div class="detail-title">操作建议</div>
            <div class="advice-grid">
              <div
                v-for="m in advice.metrics || []"
                :key="m.key"
                :class="['advice-metric', m.tone]"
              >
                <span>{{ m.label }}</span>
                <strong>{{ m.value }}</strong>
              </div>
            </div>

            <div v-if="advice.focusLines?.length" class="focus-lines">
              <div class="focus-lines-title">主线状态</div>
              <div
                v-for="f in advice.focusLines"
                :key="f.name"
                :class="['focus-line', f.accel]"
              >
                <b>{{ f.name }}</b>
                <span>{{ f.accelLabel }}</span>
                <em>{{ f.status }}</em>
              </div>
            </div>

            <div v-if="advice.watchHits?.length" class="watch-hits">
              <div class="focus-lines-title">
                自选重合 · {{ advice.watchHitCount }}只
                <span class="muted">≠买入指令</span>
              </div>
              <div
                v-for="h in advice.watchHits"
                :key="h.code"
                :class="['watch-hit', h.actionTone]"
              >
                <div class="watch-hit-name">
                  <b>{{ h.name }}</b>
                  <span class="muted">{{ h.focusName }}</span>
                </div>
                <div class="watch-hit-action">{{ h.action }}</div>
              </div>
            </div>
            <div v-else class="muted watch-empty">自选暂无与今日主线明显重合</div>

            <div v-if="advice.focuses?.length" class="focus-row">
              <button
                v-for="name in advice.focuses"
                :key="name"
                type="button"
                class="focus-tag"
                @click="$emit('open-sector')"
              >{{ name }}</button>
            </div>
            <p v-if="advice.note && !pageMode" class="advice-note muted">{{ advice.note }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { describeIndexVolume } from '../utils/signals'

const props = defineProps({
  indices: { type: Object, default: () => ({}) },
  marketTurnover: { type: Object, default: () => ({}) },
  marketBreadth: { type: Object, default: () => ({}) },
  overseas: { type: Object, default: null },
  conditions: { type: Array, default: () => [] },
  lamps: { type: Array, default: () => [] },
  positionRec: { type: Object, default: () => ({ redCount: 0, text: '', level: 'safe', cap: 0.8 }) },
  sentiment: { type: Object, default: () => ({ temp: 50, phase: '均衡', phaseClass: 'neutral', ladder: [] }) },
  sentimentHistory: {
    type: Object,
    default: () => ({
      day: null, temp: null, iceBand: 35, boilBand: 78, points: [], heightPoints: [], note: '',
    }),
  },
  advice: {
    type: Object,
    default: () => ({
      positionText: '--',
      style: '观察为主',
      rationale: '',
      focuses: [],
      buyAllowed: true,
      redCount: 0,
      positionLevel: 'safe',
    }),
  },
  sectorFlow: { type: Object, default: null },
  /** 盘面独立页：常显细节、三栏紧凑排版 */
  pageMode: { type: Boolean, default: false },
})
defineEmits(['toggle-lever', 'open-sector'])

const expanded = ref(false)
const showDetail = computed(() => props.pageMode || expanded.value)

const capText = computed(() => {
  const cap = props.positionRec.cap
  if (cap == null || !Number.isFinite(Number(cap))) return props.positionRec.text || '--'
  if (cap <= 0) return '0%'
  return `≤${Math.round(cap * 100)}%`
})

const primaryFocus = computed(() => {
  const lines = props.advice?.focusLines || []
  if (lines.length) return lines[0].name
  return props.advice?.focusText || '待确认'
})

const primaryAccel = computed(() => (props.advice?.focusLines || [])[0]?.accel || '')
const primaryAccelLabel = computed(() => (props.advice?.focusLines || [])[0]?.accelLabel || '')

const sectorFlowTop = computed(() => (props.sectorFlow?.list || [])[0] || null)
const sectorFlowBottom = computed(() => {
  const list = props.sectorFlow?.list || []
  if (!list.length) return null
  return [...list].sort((a, b) => a.netInflow - b.netInflow)[0] || null
})
const sectorFlowBrief = computed(() => {
  const top = sectorFlowTop.value
  const bot = sectorFlowBottom.value
  if (!top && !bot) return ''
  const inName = top?.sectorName || '--'
  const inAmt = top != null
    ? `${top.netInflow > 0 ? '+' : ''}${Number(top.netInflow).toFixed(0)}亿`
    : ''
  const outName = bot?.sectorName || '--'
  return `流入${inName}${inAmt}`
    + (outName && outName !== inName ? ` / 流出${outName}` : '')
})
const sectorFlowTip = computed(() => {
  const top = sectorFlowTop.value
  const bot = sectorFlowBottom.value
  if (!top && !bot) return '点击查看板块资金流'
  const parts = []
  if (top) {
    parts.push(`流入Top1 ${top.sectorName} ${top.netInflow > 0 ? '+' : ''}${Number(top.netInflow).toFixed(1)}亿`)
  }
  if (bot) {
    parts.push(`流出Top1 ${bot.sectorName} ${Number(bot.netInflow).toFixed(1)}亿`)
  }
  parts.push('点击查看双向榜')
  return parts.join(' · ')
})

const mapHint = computed(() => {
  if (props.advice?.readyCount) return '过门禁优先看'
  if (props.advice?.watchHitCount) return '展开看动作'
  return '强度前排无重合'
})

const cycle = computed(() => props.sentiment?.cycle || props.advice?.cycle || null)
const cycleLabel = computed(() => cycle.value?.label || '')
const cycleTip = computed(() => cycle.value?.tip || '')
const cycleReason = computed(() => {
  const c = cycle.value
  if (!c?.reason) return ''
  const conf = c.conf === 'high' ? '高置信' : c.conf === 'medium' ? '中置信' : '低置信'
  return `阶段假说 · ${conf} · ${c.reason}`
})
const cycleSteps = computed(() => cycle.value?.steps || [])
const cycleIndex = computed(() => {
  const i = Number(cycle.value?.index)
  return Number.isFinite(i) ? i : -1
})
const cycleClass = computed(() => {
  const id = cycle.value?.id
  if (!id) return ''
  if (id === 'ice' || id === 'retreat') return 'cold'
  if (id === 'climax' || id === 'diverge') return 'hot'
  if (id === 'ferment') return 'warm'
  return 'neutral'
})

/** 半圆弧进度 0–100（配合 SVG pathLength=100） */
const tempArc = computed(() => {
  const t = Number(props.sentiment?.temp)
  if (!Number.isFinite(t)) return 50
  return Math.max(0, Math.min(100, Math.round(t)))
})

const spark = computed(() => {
  const hist = props.sentimentHistory || {}
  const iceBand = Number(hist.iceBand)
  const boilBand = Number(hist.boilBand)
  const band = Number.isFinite(iceBand) ? iceBand : 35
  const boil = Number.isFinite(boilBand) ? boilBand : 78
  const rangeLabel = hist.rangeLabel || '近一月'
  const raw = Array.isArray(hist.points) ? hist.points : []
  const liveTemp = Number(props.sentiment?.temp)
  const points = raw
    .map((p) => ({
      t: String(p.t || ''),
      day: String(p.day || ''),
      v: Number(p.v),
      live: !!p.live,
    }))
    .filter((p) => p.t && Number.isFinite(p.v))

  // 末点：今日实时温度（前端盘面刷新立刻跟上）；周末不虚构交易日点
  const wd = new Date().getDay()
  const isWeekend = wd === 0 || wd === 6
  if (points.length && Number.isFinite(liveTemp)) {
    const last = points[points.length - 1]
    if (last.live) {
      last.v = liveTemp
    } else {
      const today = new Date()
      const y = today.getFullYear()
      const m = String(today.getMonth() + 1).padStart(2, '0')
      const d = String(today.getDate()).padStart(2, '0')
      const iso = `${y}-${m}-${d}`
      if (!last.day || last.day === iso) {
        last.v = liveTemp
        last.live = true
      } else if (!isWeekend) {
        points.push({
          t: `${m}-${d}`,
          day: iso,
          v: liveTemp,
          live: true,
        })
      }
    }
  } else if (!points.length && Number.isFinite(liveTemp) && !isWeekend) {
    const today = new Date()
    const m = String(today.getMonth() + 1).padStart(2, '0')
    const d = String(today.getDate()).padStart(2, '0')
    points.push({
      t: `${m}-${d}`,
      day: `${today.getFullYear()}-${m}-${d}`,
      v: liveTemp,
      live: true,
    })
  }

  const padX = 6
  const padY = 6
  const w = 240
  const h = 78
  const n = points.length
  const yAt = (v) => {
    const vv = Math.max(0, Math.min(100, Number(v) || 0))
    return padY + (1 - vv / 100) * (h - padY * 2)
  }
  const mapped = points.map((p, i) => {
    const x = n <= 1 ? w / 2 : padX + (i / (n - 1)) * (w - padX * 2)
    const y = yAt(p.v)
    return { ...p, x, y }
  })
  let polyPts = mapped
  if (mapped.length === 1) {
    const p = mapped[0]
    polyPts = [
      { ...p, x: Math.max(padX, p.x - 12) },
      p,
      { ...p, x: Math.min(w - padX, p.x + 12) },
    ]
  }
  const lastPt = mapped[mapped.length - 1] || null
  return {
    iceBand: band,
    boilBand: boil,
    rangeLabel,
    points: mapped,
    poly: polyPts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '),
    last: lastPt,
    firstT: mapped[0]?.t || '',
    lastT: lastPt?.t || '',
    yAt,
  }
})

const heightSpark = computed(() => {
  const hist = props.sentimentHistory || {}
  const raw = Array.isArray(hist.heightPoints) ? hist.heightPoints : []
  const liveH = Number(props.sentiment?.maxDays ?? hist.maxDays)
  const points = raw
    .map((p) => ({
      t: String(p.t || ''),
      day: String(p.day || ''),
      v: Number(p.v),
      live: !!p.live,
    }))
    .filter((p) => p.t && Number.isFinite(p.v) && p.v >= 0)

  const wd = new Date().getDay()
  const isWeekend = wd === 0 || wd === 6
  if (points.length && Number.isFinite(liveH) && liveH > 0) {
    const last = points[points.length - 1]
    if (last.live || isWeekend) last.v = liveH
    else {
      const today = new Date()
      const y = today.getFullYear()
      const m = String(today.getMonth() + 1).padStart(2, '0')
      const d = String(today.getDate()).padStart(2, '0')
      const iso = `${y}-${m}-${d}`
      if (last.day === iso) {
        last.v = liveH
        last.live = true
      } else if (!isWeekend) {
        points.push({ t: `${m}-${d}`, day: iso, v: liveH, live: true })
      }
    }
  } else if (!points.length && Number.isFinite(liveH) && liveH > 0 && !isWeekend) {
    const today = new Date()
    const m = String(today.getMonth() + 1).padStart(2, '0')
    const d = String(today.getDate()).padStart(2, '0')
    points.push({
      t: `${m}-${d}`,
      day: `${today.getFullYear()}-${m}-${d}`,
      v: liveH,
      live: true,
    })
  }

  const padX = 6
  const padY = 6
  const w = 240
  const h = 56
  const maxV = Math.max(5, ...points.map((p) => p.v), Number.isFinite(liveH) ? liveH : 0)
  const n = points.length
  const yAt = (v) => {
    const vv = Math.max(0, Math.min(maxV, Number(v) || 0))
    return padY + (1 - vv / maxV) * (h - padY * 2)
  }
  const mapped = points.map((p, i) => {
    const x = n <= 1 ? w / 2 : padX + (i / (n - 1)) * (w - padX * 2)
    return { ...p, x, y: yAt(p.v) }
  })
  let polyPts = mapped
  if (mapped.length === 1) {
    const p = mapped[0]
    polyPts = [
      { ...p, x: Math.max(padX, p.x - 12) },
      p,
      { ...p, x: Math.min(w - padX, p.x + 12) },
    ]
  }
  const lastPt = mapped[mapped.length - 1] || null
  const now = Number.isFinite(liveH) && liveH > 0
    ? liveH
    : (lastPt?.v ?? null)
  return {
    points: mapped,
    poly: polyPts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '),
    last: lastPt,
    firstT: mapped[0]?.t || '',
    lastT: lastPt?.t || '',
    now,
  }
})

const tempVsBand = computed(() => {
  const t = Number(props.sentiment?.temp)
  if (!Number.isFinite(t)) return ''
  if (t >= spark.value.boilBand) return '过热区'
  if (t <= spark.value.iceBand) return '冰点区'
  if (t >= 62) return '偏暖'
  return '一般'
})
const indexNames = {
  sh000001: '上证',
  sz399001: '深成',
  sz399006: '创业',
  sh000688: '科创',
  sh000300: '沪深',
}

const indexVolCache = computed(() => {
  const out = {}
  for (const code of Object.keys(indexNames)) {
    out[code] = describeIndexVolume(props.indices?.[code])
  }
  return out
})

function indexVol(code) {
  return indexVolCache.value[code] || describeIndexVolume(null)
}

function fmtWanYi(yi) {
  const n = Number(yi)
  if (!(n > 0) || !Number.isFinite(n)) return '--'
  if (n >= 10000) return `${(n / 10000).toFixed(2)}万亿`
  if (n >= 1000) return `${(n / 10000).toFixed(2)}万亿`
  return `${Math.round(n)}亿`
}

const turnoverAmountText = computed(() => fmtWanYi(props.marketTurnover?.amountYi))
const turnoverDeltaText = computed(() => {
  const d = props.marketTurnover?.deltaYi
  if (d == null || !Number.isFinite(Number(d))) {
    return props.marketTurnover?.ready === false ? '拉取中' : '--'
  }
  const n = Number(d)
  const abs = Math.abs(n)
  const body = abs >= 1000 ? `${(abs / 10000).toFixed(2)}万亿` : `${Math.round(abs)}亿`
  return `${n >= 0 ? '+' : '-'}${body}`
})
const turnoverTone = computed(() => {
  const d = props.marketTurnover?.deltaYi
  if (d == null || !Number.isFinite(Number(d))) return ''
  if (Number(d) > 50) return 'up'
  if (Number(d) < -50) return 'down'
  return 'flat'
})
const turnoverTip = computed(() => {
  const t = props.marketTurnover || {}
  return [t.source, t.deltaSource, t.note].filter(Boolean).join(' · ')
})

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

/** 灯牌一行短因：去掉过长括号说明 */
function lampWhy(l) {
  const d = String(l?.detail || '').trim()
  if (!d) return ''
  if (d.length <= 18) return d
  return `${d.slice(0, 16)}…`
}
</script>

<style scoped>
.market-bar {
  display: flex;
  gap: 4px;
  align-items: stretch;
  padding: 6px 0 4px;
  overflow: hidden;
  flex-wrap: nowrap;
}
.turn-card,
.idx-card,
.ov-card {
  min-width: 0;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--chip-bg);
}
.turn-card {
  flex: 1.2 1 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 1px;
}
.turn-card .row1,
.turn-card .row2,
.idx-card .row1,
.idx-card .row2 {
  display: flex;
  align-items: baseline;
  gap: 5px;
  min-width: 0;
  white-space: nowrap;
}
.turn-card .name,
.idx-card .name,
.ov-card .name {
  font-size: 10px;
  font-weight: 700;
  color: var(--muted);
  flex-shrink: 0;
}
.turn-card .amt {
  font-size: 12px;
  font-weight: 700;
  color: var(--bright);
  font-variant-numeric: tabular-nums;
}
.turn-card .sub {
  font-size: 10px;
  color: var(--muted);
}
.turn-card .delta {
  margin-left: auto;
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.turn-card.up .delta { color: var(--red); }
.turn-card.down .delta { color: var(--green); }
.turn-card.flat .delta { color: var(--bright); }

.idx-card {
  flex: 1.05 1 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 1px;
}
.idx-card .price {
  flex: 1;
  min-width: 0;
  font-size: 11px;
  font-weight: 600;
  color: var(--bright);
  font-variant-numeric: tabular-nums;
  overflow: hidden;
  text-overflow: ellipsis;
}
.idx-card .chg,
.ov-card .chg {
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.idx-card .row2 {
  color: var(--muted);
  font-size: 10px;
}
.idx-card .tag { font-weight: 700; flex-shrink: 0; }
.idx-card .lb {
  font-variant-numeric: tabular-nums;
  opacity: 0.85;
}
.idx-card .amt {
  margin-left: auto;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.idx-card.expand .row2,
.idx-card.mild .row2 { color: var(--red); }
.idx-card.shrink .row2 { color: var(--green); }
.idx-card.flat .row2 { color: var(--bright); }

.ov-card {
  flex: 0.55 1 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0;
  padding: 4px 5px;
}
.ov-card .chg { font-size: 12px; }

@media (max-width: 1280px) {
  .ov-card { display: none; }
}
@media (max-width: 1200px) {
  .idx-card .price,
  .idx-card .lb { display: none; }
}

.cmd-strip {
  display: grid;
  grid-template-columns: 1.15fr 1fr 1.25fr 0.95fr auto;
  gap: 0;
  margin: 2px 0 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, var(--card-bg) 0%, var(--hover-soft, rgba(139,148,158,0.06)) 100%);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.cmd-strip:hover,
.cmd-strip.open {
  border-color: rgba(88, 166, 255, 0.45);
  box-shadow: 0 0 0 1px rgba(88, 166, 255, 0.12);
}
.cmd-strip:focus-visible {
  outline: 2px solid var(--blue);
  outline-offset: 2px;
}

.cmd-seg {
  min-width: 0;
  padding: 6px 10px;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 2px;
  justify-content: center;
}
.cmd-seg.focus {
  cursor: pointer;
}
.cmd-seg.focus:hover .focus-name,
.cmd-seg.focus:hover .flow-brief { color: var(--blue); }
.cmd-seg.cap.danger { background: linear-gradient(90deg, var(--red-bg), transparent); }
.cmd-seg.cap.warning { background: linear-gradient(90deg, var(--orange-bg), transparent); }
.cmd-seg.cap.safe { background: linear-gradient(90deg, var(--green-bg), transparent); }

.seg-label {
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--muted);
  text-transform: uppercase;
}
.seg-main {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}
.seg-main strong {
  font-size: 16px;
  color: var(--bright);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.seg-main .muted-strong {
  font-size: 15px;
  color: var(--muted);
  font-weight: 600;
}
.seg-flag {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid var(--border);
}
.seg-flag.ok { color: var(--blue); background: var(--blue-bg); }
.seg-flag.no { color: var(--red); background: var(--red-bg); border-color: rgba(248,81,73,0.35); }

.lamp-dots {
  display: flex;
  gap: 4px;
  margin-top: 2px;
}
.lamp-dots .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(139, 148, 158, 0.35);
  border: 1px solid transparent;
}
.lamp-dots .dot.on.hard { background: var(--red); box-shadow: 0 0 6px rgba(248, 81, 73, 0.45); }
.lamp-dots .dot.on.soft {
  background: var(--orange);
  border-style: dashed;
  box-shadow: 0 0 5px rgba(210, 153, 34, 0.35);
}
.lamp-dots .dot.manual { cursor: pointer; }

.phase-text {
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.phase-text.hot { color: var(--red); }
.phase-text.warm { color: var(--orange); }
.phase-text.neutral { color: var(--blue); }
.phase-text.cold { color: var(--green); }

.mood-text-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 0;
}
.phase-sub {
  font-size: 10px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mood-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.cycle-track {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 4px;
  margin: 0 0 8px;
}
.cycle-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
  position: relative;
}
.cycle-step i {
  width: 100%;
  height: 4px;
  border-radius: 2px;
  background: rgba(139, 148, 158, 0.25);
}
.cycle-step span {
  font-size: 10px;
  color: var(--muted);
  white-space: nowrap;
}
.cycle-step.passed i { background: rgba(88, 166, 255, 0.45); }
.cycle-step.passed span { color: var(--blue); }
.cycle-step.active i {
  background: var(--orange);
  box-shadow: 0 0 6px rgba(210, 153, 34, 0.35);
}
.cycle-step.active span {
  color: var(--bright);
  font-weight: 700;
}
.cycle-step.active.ice i,
.cycle-step.active.retreat i { background: var(--green); box-shadow: 0 0 6px rgba(63, 185, 80, 0.3); }
.cycle-step.active.climax i,
.cycle-step.active.diverge i { background: var(--red); box-shadow: 0 0 6px rgba(248, 81, 73, 0.35); }
.cycle-step.active.ferment i { background: var(--orange); }
.cycle-reason {
  font-size: 11px;
  margin: 0 0 10px;
  line-height: 1.4;
}

.temp-gauge {
  position: relative;
  flex-shrink: 0;
}
.temp-gauge.mini {
  width: 56px;
  height: 36px;
}
.gauge-svg {
  width: 100%;
  height: 100%;
  display: block;
}
.gauge-track {
  fill: none;
  stroke: rgba(139, 148, 158, 0.28);
  stroke-width: 7;
  stroke-linecap: round;
}
.gauge-fill {
  fill: none;
  stroke: var(--blue);
  stroke-width: 7;
  stroke-linecap: round;
  transition: stroke-dasharray 0.35s ease;
}
.temp-gauge.hot .gauge-fill { stroke: var(--red); }
.temp-gauge.warm .gauge-fill { stroke: var(--orange); }
.temp-gauge.neutral .gauge-fill { stroke: var(--blue); }
.temp-gauge.cold .gauge-fill { stroke: var(--green); }

.gauge-readout {
  position: absolute;
  left: 50%;
  bottom: 2px;
  transform: translateX(-50%);
  text-align: center;
  line-height: 1.05;
  pointer-events: none;
}
.gauge-readout b {
  display: block;
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--bright);
}

.mood-detail-head {
  display: grid;
  grid-template-columns: minmax(120px, 0.9fr) minmax(0, 1.4fr);
  gap: 12px;
  align-items: stretch;
  margin-bottom: 8px;
}
.mood-now {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.mood-now-temp {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}
.mood-now-temp b {
  font-size: 28px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  color: var(--bright);
}
.mood-now-temp .mood-unit {
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  margin-left: -2px;
}
.mood-now-temp .mood-phase {
  font-size: 13px;
  font-weight: 700;
}
.mood-now-temp span {
  font-size: 12px;
  font-weight: 700;
}
.mood-now-temp.hot span, .mood-now-temp.hot b { color: var(--red); }
.mood-now-temp.warm span, .mood-now-temp.warm b { color: var(--orange); }
.mood-now-temp.neutral span { color: var(--blue); }
.mood-now-temp.cold span, .mood-now-temp.cold b { color: var(--green); }
.mood-band-hint {
  font-size: 11px;
  line-height: 1.35;
}
.mood-band-hint em {
  font-style: normal;
  color: var(--bright);
  font-weight: 600;
}

.mood-charts {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.mood-spark-wrap {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.spark-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
}
.mood-spark {
  width: 100%;
  height: 78px;
  display: block;
  border-radius: 8px;
  background: rgba(22, 27, 34, 0.35);
  border: 1px solid var(--border);
}
.mood-spark.height-spark { height: 56px; }
.mood-spark .ice-band {
  fill: rgba(63, 185, 80, 0.12);
}
.mood-spark .boil-band {
  fill: rgba(248, 81, 73, 0.10);
}
.mood-spark .ice-line {
  stroke: rgba(63, 185, 80, 0.55);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}
.mood-spark .boil-line {
  stroke: rgba(248, 81, 73, 0.55);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}
.mood-spark .band-label {
  font-size: 8px;
  fill: var(--muted);
}
.mood-spark .band-label.ice { fill: rgba(63, 185, 80, 0.85); }
.mood-spark .band-label.boil { fill: rgba(248, 81, 73, 0.85); }
.mood-spark .spark-line {
  stroke: var(--blue);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
  fill: none;
}
.mood-spark .spark-line.height {
  stroke: var(--orange);
  stroke-width: 1.6;
}
.mood-spark .spark-dot {
  fill: var(--blue);
  stroke: rgba(255, 255, 255, 0.35);
  stroke-width: 1;
}
.mood-spark .spark-dot.hot { fill: var(--red); }
.mood-spark .spark-dot.warm { fill: var(--orange); }
.mood-spark .spark-dot.cold { fill: var(--green); }
.mood-spark .spark-dot.live {
  stroke: rgba(255, 255, 255, 0.7);
  stroke-width: 1.5;
}
.mood-spark-empty {
  height: 78px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px dashed var(--border);
  font-size: 12px;
}
.mood-spark-empty.short { height: 56px; font-size: 11px; }
.spark-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 10px;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.breadth-stats.stacked {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 0;
}

.focus-name {
  font-size: 14px !important;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.accel-tag {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--muted);
}
.accel-tag.accelerating { color: var(--red); background: var(--red-bg); border-color: rgba(248,81,73,0.35); }
.accel-tag.fading { color: var(--green); background: var(--green-bg); border-color: rgba(63,185,80,0.35); }
.accel-tag.holding { color: var(--blue); background: var(--blue-bg); }

.seg-sub {
  font-size: 11px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.flow-brief {
  color: var(--muted);
}

.cmd-chevron {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 0 12px;
  color: var(--muted);
  font-size: 11px;
  background: var(--hover-soft, rgba(139,148,158,0.05));
  min-width: 52px;
}
.cmd-chevron em {
  font-style: normal;
  font-size: 14px;
  transition: transform 0.15s ease;
  line-height: 1;
}
.cmd-chevron em.open { transform: rotate(180deg); }
.cmd-strip:hover .cmd-chevron { color: var(--blue); }

.cmd-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 0 12px;
}
.detail-lamps {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--hover-soft, rgba(139, 148, 158, 0.06));
  padding: 8px 12px;
  min-width: 0;
}
.detail-lamps-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.detail-lamps-head .detail-title { margin-bottom: 0; }
.lamp-cap {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
  min-width: 0;
}
.lamp-cap strong {
  font-size: 15px;
  color: var(--bright);
}
.lamp-cap.danger strong { color: var(--red); }
.lamp-cap.warning strong { color: var(--orange); }
.lamp-cap.safe strong { color: var(--green); }
.lamp-cap em {
  font-style: normal;
  font-size: 11px;
  color: var(--muted);
}
.detail-main {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 10px;
  align-items: start;
}
.detail-col {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--hover-soft, rgba(139, 148, 158, 0.06));
  padding: 10px 12px;
  min-width: 0;
}
.detail-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--bright);
  margin-bottom: 8px;
}
.detail-note { font-size: 11px; margin-top: 6px; line-height: 1.4; }
.lamp-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
}
.lamp {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 3px;
  min-width: 0;
  padding: 7px 8px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--card-bg);
  font-size: 12px;
  color: var(--bright);
  line-height: 1.25;
}
.lamp-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.lamp .ball {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--green);
}
.lamp.red .ball { background: var(--red); box-shadow: 0 0 6px rgba(248, 81, 73, 0.4); }
.lamp.green .ball { background: var(--green); }
.lamp-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lamp-why {
  display: block;
  width: 100%;
  font-size: 10px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lamp.soft { opacity: 0.92; border-style: dashed; }
.lamp small { margin-left: 0; opacity: 0.85; color: var(--orange); flex-shrink: 0; }

.breadth-stats {
  display: flex; flex-wrap: wrap; gap: 8px 12px;
  font-size: 12px; color: var(--muted); margin-bottom: 8px;
}
.effect-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px;
}
.effect-chip {
  border: 1px solid var(--border); border-radius: 8px; padding: 5px 8px; background: var(--card-bg);
}
.effect-chip span { display: block; font-size: 10px; color: var(--muted); }
.effect-chip strong {
  display: block; margin-top: 2px; font-size: 12px; color: var(--bright);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.effect-chip.good strong { color: var(--red); }
.effect-chip.bad strong { color: var(--green); }
.ladder-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.ladder-chip {
  display: inline-flex; gap: 4px; align-items: center;
  padding: 2px 7px; border-radius: 6px; border: 1px solid var(--border);
  font-size: 11px; color: var(--muted); background: var(--card-bg);
}
.ladder-chip b { color: var(--bright); }
.cond-row { display: flex; flex-wrap: wrap; gap: 6px; }

.advice-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 8px;
}
.advice-metric {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--card-bg);
  min-width: 0;
}
.advice-metric span {
  display: block;
  font-size: 11px;
  color: var(--muted);
}
.advice-metric strong {
  display: block;
  margin-top: 4px;
  font-size: 14px;
  color: var(--bright);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.advice-metric.danger strong,
.advice-metric.warn strong { color: var(--orange); }
.advice-metric.safe strong { color: var(--green); }
.advice-metric.focus strong { color: var(--blue); }
.advice-metric.ready strong { color: var(--red); }
.advice-metric.watch strong { color: var(--blue); }

.focus-lines, .watch-hits { margin-top: 8px; }
.focus-lines-title {
  font-size: 11px; color: var(--muted); margin-bottom: 6px;
  display: flex; gap: 8px; align-items: baseline;
}
.focus-line, .watch-hit {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 5px 8px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--card-bg); margin-bottom: 5px; font-size: 12px;
}
.focus-line b, .watch-hit-name b { color: var(--bright); }
.focus-line span { color: var(--muted); }
.focus-line em { font-style: normal; font-size: 11px; color: var(--blue); }
.focus-line.accelerating { border-color: rgba(248, 81, 73, 0.35); }
.focus-line.fading { border-color: rgba(63, 185, 80, 0.35); }
.watch-hit { justify-content: space-between; }
.watch-hit-name { display: flex; gap: 6px; align-items: baseline; min-width: 0; }
.watch-hit-action { font-size: 11px; color: var(--muted); white-space: nowrap; }
.watch-hit.ready .watch-hit-action { color: var(--red); font-weight: 700; }
.watch-hit.gate .watch-hit-action { color: var(--orange); }
.watch-hit.block .watch-hit-action { color: var(--green); }
.watch-hit.hold .watch-hit-action { color: var(--teal, #2dd4bf); }
.watch-empty { font-size: 11px; margin-top: 6px; }
.advice-note { margin: 8px 0 0; font-size: 11px; line-height: 1.4; }

.focus-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.focus-tag {
  border: 1px solid var(--border); background: var(--card-bg); color: var(--blue);
  border-radius: 999px; padding: 2px 8px; font-size: 11px; cursor: pointer;
}
.focus-tag:hover { border-color: var(--blue); background: var(--blue-bg); }

@media (max-width: 1100px) {
  .cmd-strip {
    grid-template-columns: 1fr 1fr;
  }
  .cmd-seg.map { border-right: 0; }
  .cmd-chevron {
    grid-column: 1 / -1;
    flex-direction: row;
    gap: 6px;
    padding: 8px;
    border-top: 1px solid var(--border);
  }
  .detail-main { grid-template-columns: 1fr; }
  .lamp-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .mood-detail-head { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .cmd-strip { grid-template-columns: 1fr; }
  .cmd-seg { border-right: 0; border-bottom: 1px solid var(--border); }
  .lamp-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

/* —— 盘面独立页：一屏三栏 —— */
.page-mode {
  margin-bottom: 6px;
}
.page-mode .cmd-strip {
  margin: 2px 0 6px;
  grid-template-columns: 1.15fr 1fr 1.25fr 0.95fr;
  cursor: default;
}
.page-mode .cmd-strip.static:hover {
  border-color: var(--border);
  box-shadow: none;
}
.page-mode .cmd-detail {
  display: grid;
  grid-template-columns: minmax(168px, 0.85fr) minmax(0, 1.25fr) minmax(0, 1.1fr);
  gap: 8px;
  padding: 0 0 6px;
  align-items: stretch;
}
.page-mode .detail-main {
  display: contents;
}
.page-mode .detail-lamps,
.page-mode .detail-col {
  padding: 8px 10px;
  min-height: 0;
}
.page-mode .detail-title { margin-bottom: 6px; }
.page-mode .detail-lamps-head { margin-bottom: 6px; }
.page-mode .lamp-row {
  grid-template-columns: 1fr;
  gap: 4px;
}
.page-mode .lamp {
  padding: 5px 7px;
  gap: 1px;
}
.page-mode .detail-note {
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.page-mode .mood-detail-head {
  grid-template-columns: minmax(90px, 0.7fr) minmax(0, 1.3fr);
  gap: 8px;
  margin-bottom: 6px;
}
.page-mode .mood-spark {
  height: 52px;
}
.page-mode .mood-spark.height-spark {
  height: 40px;
}
.page-mode .mood-now-temp b { font-size: 22px; }
.page-mode .spark-title { font-size: 10px; }
.page-mode .effect-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
  margin-bottom: 6px;
}
.page-mode .effect-chip { padding: 4px 6px; }
.page-mode .ladder-row,
.page-mode .cond-row { margin-bottom: 0; gap: 4px; }
.page-mode .advice-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
  margin-bottom: 6px;
}
.page-mode .advice-metric { padding: 5px 7px; }
.page-mode .advice-metric strong { font-size: 13px; margin-top: 2px; }
.page-mode .focus-lines,
.page-mode .watch-hits { margin-top: 6px; }
.page-mode .focus-line,
.page-mode .watch-hit {
  padding: 4px 6px;
  margin-bottom: 4px;
}
.page-mode .focus-row { margin-top: 6px; }
@media (max-width: 1100px) {
  .page-mode .cmd-detail {
    grid-template-columns: 1fr;
  }
  .page-mode .lamp-row {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
  .page-mode .effect-grid,
  .page-mode .advice-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
