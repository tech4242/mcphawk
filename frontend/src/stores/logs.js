import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { parseMessage, getMessageType } from '@/utils/messageParser'

export const useLogStore = defineStore('logs', () => {
  // State
  const logs = ref([])
  const filter = ref('all')
  const searchQuery = ref('')
  const showPairing = ref(false)
  const selectedLogId = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const expandAll = ref(false)
  const showMcpHawkTraffic = ref(false)

  // Computed
  const filteredLogs = computed(() => {
    let result = logs.value

    // Filter out MCPHawk's own traffic if toggle is off
    if (!showMcpHawkTraffic.value) {
      result = result.filter(log => {
        if (!log.metadata) return true
        try {
          const meta = JSON.parse(log.metadata)
          return meta.source !== 'mcphawk-mcp'
        } catch {
          return true
        }
      })
    }

    // Apply type filter
    if (filter.value !== 'all') {
      result = result.filter(log => {
        const msgType = getMessageType(log.message)
        return msgType === filter.value
      })
    }

    // Apply search
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      result = result.filter(log => {
        return JSON.stringify(log).toLowerCase().includes(query)
      })
    }

    return result
  })

  const stats = computed(() => {
    const stats = {
      total: logs.value.length,
      requests: 0,
      responses: 0,
      notifications: 0,
      errors: 0,
      mcphawk: 0
    }

    logs.value.forEach(log => {
      const msgType = getMessageType(log.message)
      if (msgType === 'request') stats.requests++
      else if (msgType === 'response') stats.responses++
      else if (msgType === 'notification') stats.notifications++
      else if (msgType === 'error') stats.errors++
      
      // Count MCPHawk's own traffic
      if (log.metadata) {
        try {
          const meta = JSON.parse(log.metadata)
          if (meta.source === 'mcphawk-mcp') stats.mcphawk++
        } catch {
          // ignore parse errors
        }
      }
    })

    return stats
  })

  const selectedLog = computed(() => {
    return logs.value.find(log => log.log_id === selectedLogId.value)
  })

  const pairedLogs = computed(() => {
    if (!showPairing.value || !selectedLog.value) return new Set()
    
    const parsed = parseMessage(selectedLog.value.message)
    if (!parsed || !parsed.id) return new Set()
    
    const paired = new Set()
    logs.value.forEach(log => {
      const logParsed = parseMessage(log.message)
      if (logParsed && logParsed.id === parsed.id) {
        paired.add(log.log_id)
      }
    })
    
    return paired
  })

  // Actions
  async function fetchLogs(limit = 100) {
    loading.value = true
    error.value = null
    
    try {
      const response = await axios.get('/logs', {
        params: { limit }
      })
      logs.value = response.data
    } catch (err) {
      error.value = err.message
      console.error('Failed to fetch logs:', err)
    } finally {
      loading.value = false
    }
  }

  function addLog(log) {
    // Add to beginning for newest first
    logs.value.unshift(log)
    
    // Limit to 10000 logs in memory
    if (logs.value.length > 10000) {
      logs.value = logs.value.slice(0, 10000)
    }
  }

  function clearLogs() {
    logs.value = []
    selectedLogId.value = null
  }

  function selectLog(logId) {
    selectedLogId.value = logId
  }

  function setFilter(newFilter) {
    filter.value = newFilter
  }

  function setSearchQuery(query) {
    searchQuery.value = query
  }

  function togglePairing() {
    showPairing.value = !showPairing.value
  }

  function toggleExpandAll() {
    expandAll.value = !expandAll.value
  }

  function toggleMcpHawkTraffic() {
    showMcpHawkTraffic.value = !showMcpHawkTraffic.value
  }

  return {
    // State
    logs,
    filter,
    searchQuery,
    showPairing,
    selectedLogId,
    loading,
    error,
    expandAll,
    showMcpHawkTraffic,
    
    // Computed
    filteredLogs,
    stats,
    selectedLog,
    pairedLogs,
    
    // Actions
    fetchLogs,
    addLog,
    clearLogs,
    selectLog,
    setFilter,
    setSearchQuery,
    togglePairing,
    toggleExpandAll,
    toggleMcpHawkTraffic
  }
})