export function parseMessage(message) {
  try {
    if (typeof message === 'string') {
      return JSON.parse(message)
    }
    return message
  } catch (err) {
    return null
  }
}

export function getMessageType(message) {
  const parsed = parseMessage(message)
  if (!parsed) return 'unknown'
  
  // Check if it's a valid JSON-RPC message
  if (!parsed.jsonrpc || parsed.jsonrpc !== '2.0') {
    return 'unknown'
  }
  
  // Error response
  if (parsed.error && parsed.id !== undefined) {
    return 'error'
  }
  
  // Response (has result and id)
  if ('result' in parsed && parsed.id !== undefined) {
    return 'response'
  }
  
  // Request (has method and id)
  if (parsed.method && parsed.id !== undefined) {
    return 'request'
  }
  
  // Notification (has method but no id)
  if (parsed.method && parsed.id === undefined) {
    return 'notification'
  }
  
  return 'unknown'
}

export function getMethodName(message) {
  const parsed = parseMessage(message)
  return parsed?.method || null
}

export function formatTimestamp(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3
  })
}

export function formatDate(timestamp) {
  const date = new Date(timestamp)
  const day = date.getDate().toString().padStart(2, '0')
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const year = date.getFullYear()
  return `${day}:${month}:${year}`
}

export function getMessageSummary(message) {
  const parsed = parseMessage(message)
  if (!parsed) return 'Invalid JSON'
  
  const type = getMessageType(message)
  
  switch (type) {
    case 'request':
      return `${parsed.method}(${parsed.id})`
    case 'response':
      return `Response(${parsed.id})`
    case 'notification':
      return `${parsed.method}`
    case 'error':
      return `Error(${parsed.id}): ${parsed.error.message}`
    default:
      return 'Unknown message type'
  }
}

export function getPortInfo(log) {
  return `${log.src_port || '?'} → ${log.dst_port || '?'}`
}

export function getDirectionIcon(direction) {
  switch (direction) {
    case 'incoming':
      return '←'
    case 'outgoing':
      return '→'
    default:
      return '↔'
  }
}