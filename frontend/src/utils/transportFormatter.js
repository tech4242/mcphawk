/**
 * Format transport type for display
 */
export function formatTransportType(transportType) {
  const transportMap = {
    'streamable_http': 'Streamable HTTP',
    'http_sse': 'HTTP+SSE',
    'stdio': 'stdio',
    'unknown': 'Unknown',
    // Legacy values
    'TCP/Direct': 'Unknown',
    'N/A': 'Unknown'
  }
  
  return transportMap[transportType] || 'Unknown'
}

/**
 * Get transport type badge color
 */
export function getTransportTypeColor(transportType) {
  const colorMap = {
    'streamable_http': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    'http_sse': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    'stdio': 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    'unknown': 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
  }
  
  return colorMap[transportType] || colorMap['unknown']
}