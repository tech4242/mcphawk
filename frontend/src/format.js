export function call(exchange) {
  return exchange.target ? `${exchange.method} ${exchange.target}` : exchange.method
}

export function ms(value) {
  if (value === null || value === undefined) return ''
  if (value < 1) return '<1 ms'
  if (value < 1000) return `${Math.round(value)} ms`
  if (value < 60000) return `${(value / 1000).toFixed(1)} s`
  return `${Math.floor(value / 60000)} m ${Math.round((value % 60000) / 1000)} s`
}

export function tokens(value) {
  if (!value) return '0'
  return value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(value)
}

export function when(epoch) {
  if (!epoch) return ''
  const date = new Date(epoch * 1000)
  const today = new Date().toDateString() === date.toDateString()
  return today
    ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export const STATUS_LABELS = {
  ok: 'ok',
  error: 'error',
  tool_error: 'tool error',
  input_required: 'needs input',
  cancelled: 'cancelled',
  pending: 'waiting',
  hung: 'no reply',
  abandoned: 'unanswered',
}

// Distinct, colour-blind-considerate hues for servers within one run.
const SERVER_HUES = ['#7aa2f7', '#e0af68', '#9ece6a', '#bb9af7', '#7dcfff', '#ff9e64', '#c0caf5', '#f7768e']
export function serverColor(index) {
  return SERVER_HUES[index % SERVER_HUES.length]
}

export function timeRange(start, end) {
  if (!start) return ''
  const opts = { hour: '2-digit', minute: '2-digit' }
  const from = new Date(start * 1000)
  const to = new Date((end || start) * 1000)
  const day = from.toDateString() === new Date().toDateString()
    ? '' : `${from.toLocaleDateString([], { month: 'short', day: 'numeric' })}, `
  const a = from.toLocaleTimeString([], opts)
  const b = to.toLocaleTimeString([], opts)
  return a === b ? `${day}${a}` : `${day}${a}–${b}`
}
