import { match as pinyinMatch, pinyin } from 'pinyin-pro'
import { sectorFocusKeywords } from './strategy.js'

/** 汉字 → 拼音首字母，如 北方稀土 → bfxt */
export function pinyinInitials(text) {
  const s = String(text || '').trim()
  if (!s) return ''
  return pinyin(s, { pattern: 'first', toneType: 'none', type: 'array' })
    .join('')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
}

/** 汉字 → 全拼无声调，如 北方稀土 → beifangxitu */
export function pinyinFull(text) {
  const s = String(text || '').trim()
  if (!s) return ''
  return pinyin(s, { toneType: 'none', type: 'array' })
    .join('')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
}

function norm(s) {
  return String(s || '').trim().toLowerCase()
}

function latinQuery(q) {
  return /^[a-z][a-z0-9]*$/.test(q)
}

function textHit(hay, q) {
  const h = norm(hay)
  return !!h && h.includes(q)
}

function pinyinHit(text, q, cachedInitials, cachedFull) {
  if (!text || !latinQuery(q)) return false
  const initials = norm(cachedInitials) || pinyinInitials(text)
  if (initials && (initials.startsWith(q) || initials.includes(q))) return true
  const full = norm(cachedFull) || pinyinFull(text)
  if (full && full.includes(q)) return true
  try {
    if (pinyinMatch(String(text), q)) return true
  } catch {
    /* ignore */
  }
  return false
}

/**
 * 标的搜索：名称 / 代码 / 板块 / 行业 / 别名，以及名称·板块拼音首字母/全拼。
 * 例：bfxt→北方稀土，bdt→半导体，电子→PCB（别名）。
 */
export function matchStockQuery(item, rawQ) {
  const q = norm(rawQ)
  if (!q) return true

  const name = item?.name || ''
  const code = item?.code || ''
  const rawCode = item?.rawCode || String(code).replace(/^(sh|sz)/i, '')
  const sector = item?.sector || ''
  const industry = item?.industry || item?.q?.industry || ''

  if (textHit(name, q) || textHit(code, q) || textHit(rawCode, q)) return true
  if (textHit(sector, q) || textHit(industry, q)) return true

  // 板块别名：搜「电子/元件」也能落到 PCB 等 Jarvis 标签
  const aliases = sectorFocusKeywords(sector)
  if (aliases.some((k) => textHit(k, q) || (norm(k) && q.includes(norm(k))))) return true

  // 拼音：名称优先，其次板块/行业
  if (pinyinHit(name, q, item?.pyInitials, item?.pyFull)) return true
  if (pinyinHit(sector, q)) return true
  if (pinyinHit(industry, q)) return true

  return false
}

/**
 * 搜索词是否对准下方某个板块 chip（用于选中高亮）。
 * 只认标签名/拼音首字母，避免全拼误伤（如 kuai 含 ai）。
 */
export function sectorTagMatches(sectorName, rawQ) {
  const q = norm(rawQ)
  const name = String(sectorName || '').trim()
  if (!q || !name || name === '其他') return false
  const n = norm(name)
  if (n.includes(q) || (q.length >= 2 && q.includes(n))) return true
  if (!latinQuery(q)) return false
  const initials = pinyinInitials(name)
  if (initials && (initials === q || initials.startsWith(q))) return true
  try {
    if (pinyinMatch(name, q)) return true
  } catch {
    /* ignore */
  }
  return false
}
