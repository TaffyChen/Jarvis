import { marked } from 'marked'

marked.setOptions({
  gfm: true,
  breaks: true,
})

/** 去掉回答里的 json 补丁代码块（由卡片单独展示） */
export function stripPatchBlocks(text) {
  return String(text || '')
    .replace(/```json\s*\{[\s\S]*?\}\s*```/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/** 极简消毒：去掉脚本/事件处理器，保留常见排版标签 */
function sanitize(html) {
  return String(html || '')
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
    .replace(/\son\w+\s*=\s*(['"]).*?\1/gi, '')
    .replace(/\son\w+\s*=\s*[^\s>]+/gi, '')
    .replace(/javascript:/gi, '')
}

/** 用户消息：纯文本转义 */
export function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Assistant：Markdown → 安全 HTML */
export function renderAssistantHtml(text) {
  const cleaned = stripPatchBlocks(text)
  if (!cleaned) return ''
  try {
    return sanitize(marked.parse(cleaned))
  } catch {
    return `<p>${escapeHtml(cleaned)}</p>`
  }
}
