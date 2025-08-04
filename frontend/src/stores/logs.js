import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { parseMessage, getMessageType } from '@/utils/messageParser'

export const useLogStore = defineStore('logs', () => {
  // State
  const logs = ref([])
  const filter = ref('all')
  const searchQuery = ref('')
  const transportFilter = ref('all')
  const serverFilter = ref('all')
  const showPairing = ref(false)
  const selectedLogId = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const expandAll = ref(false)

  // Computed
  const filteredLogs = computed(() => {
    let result = logs.value

    // Apply type filter
    if (filter.value !== 'all') {
      result = result.filter(log => {
        const msgType = getMessageType(log.message)
        return msgType === filter.value
      })
    }

    // Apply transport filter
    if (transportFilter.value !== 'all') {
      result = result.filter(log => {
        const transport = log.transport_type || log.traffic_type || 'unknown'
        return transport === transportFilter.value
      })
    }

    // Apply server filter
    if (serverFilter.value !== 'all') {
      result = result.filter(log => {
        if (!log.metadata) return false
        try {
          const meta = JSON.parse(log.metadata)
          return meta.server_name === serverFilter.value
        } catch {
          return false
        }
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
      errors: 0
    }

    logs.value.forEach(log => {
      const msgType = getMessageType(log.message)
      if (msgType === 'request') stats.requests++
      else if (msgType === 'response') stats.responses++
      else if (msgType === 'notification') stats.notifications++
      else if (msgType === 'error') stats.errors++
    })

    return stats
  })

  const selectedLog = computed(() => {
    return logs.value.find(log => log.log_id === selectedLogId.value)
  })

  const uniqueServers = computed(() => {
    const servers = new Set()
    logs.value.forEach(log => {
      if (log.metadata) {
        try {
          const meta = JSON.parse(log.metadata)
          if (meta.server_name) {
            servers.add(meta.server_name)
          }
        } catch {
          // ignore
        }
      }
    })
    return Array.from(servers).sort()
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

  function setTransportFilter(transport) {
    transportFilter.value = transport
  }

  function setServerFilter(server) {
    serverFilter.value = server
  }

  return {
    // State
    logs,
    filter,
    searchQuery,
    transportFilter,
    serverFilter,
    showPairing,
    selectedLogId,
    loading,
    error,
    expandAll,
    
    // Computed
    filteredLogs,
    stats,
    selectedLog,
    uniqueServers,
    pairedLogs,
    
    // Actions
    fetchLogs,
    addLog,
    clearLogs,
    selectLog,
    setFilter,
    setSearchQuery,
    setTransportFilter,
    setServerFilter,
    togglePairing,
    toggleExpandAll
  }
})