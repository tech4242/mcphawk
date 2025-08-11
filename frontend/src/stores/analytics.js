import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { useLogStore } from './logs'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const useAnalyticsStore = defineStore('analytics', () => {
  // State
  const timeRange = ref({
    startTime: null,
    endTime: null,
    intervalMinutes: 5
  })
  
  const timeseries = ref(null)
  const methods = ref(null)
  const transportDistribution = ref(null)
  const messageTypes = ref(null)
  const performance = ref(null)
  const errors = ref(null)
  
  const loading = ref({
    timeseries: false,
    methods: false,
    transport: false,
    messageTypes: false,
    performance: false,
    errors: false
  })
  
  // Get filters from log store
  const logStore = useLogStore()
  
  // Computed
  const filters = computed(() => ({
    transportType: logStore.transportFilter === 'all' ? undefined : logStore.transportFilter,
    serverName: logStore.serverFilter === 'all' ? undefined : logStore.serverFilter
  }))
  
  const queryParams = computed(() => {
    const params = new URLSearchParams()
    
    if (timeRange.value.startTime) {
      params.append('start_time', timeRange.value.startTime)
    }
    if (timeRange.value.endTime) {
      params.append('end_time', timeRange.value.endTime)
    }
    if (filters.value.transportType) {
      params.append('transport_type', filters.value.transportType)
    }
    if (filters.value.serverName) {
      params.append('server_name', filters.value.serverName)
    }
    
    return params.toString()
  })
  
  // Actions
  async function fetchTimeseries() {
    loading.value.timeseries = true
    try {
      const params = queryParams.value
      const intervalParam = `interval_minutes=${timeRange.value.intervalMinutes}`
      const url = `${API_BASE_URL}/api/metrics/timeseries?${params}&${intervalParam}`
      console.log('Fetching timeseries from:', url)
      const response = await axios.get(url)
      timeseries.value = response.data
      console.log('Timeseries data received:', response.data)
    } catch (error) {
      console.error('Failed to fetch timeseries:', error)
      timeseries.value = null
    } finally {
      loading.value.timeseries = false
    }
  }
  
  async function fetchMethods() {
    loading.value.methods = true
    try {
      const params = queryParams.value
      const url = `${API_BASE_URL}/api/metrics/methods?${params}&limit=15`
      const response = await axios.get(url)
      methods.value = response.data
    } catch (error) {
      console.error('Failed to fetch methods:', error)
    } finally {
      loading.value.methods = false
    }
  }
  
  async function fetchTransportDistribution() {
    loading.value.transport = true
    try {
      const params = new URLSearchParams()
      if (timeRange.value.startTime) {
        params.append('start_time', timeRange.value.startTime)
      }
      if (timeRange.value.endTime) {
        params.append('end_time', timeRange.value.endTime)
      }
      const url = `${API_BASE_URL}/api/metrics/transport?${params.toString()}`
      const response = await axios.get(url)
      transportDistribution.value = response.data
    } catch (error) {
      console.error('Failed to fetch transport distribution:', error)
    } finally {
      loading.value.transport = false
    }
  }
  
  async function fetchMessageTypes() {
    loading.value.messageTypes = true
    try {
      const params = queryParams.value
      const url = `${API_BASE_URL}/api/metrics/message-types?${params}`
      const response = await axios.get(url)
      messageTypes.value = response.data
    } catch (error) {
      console.error('Failed to fetch message types:', error)
    } finally {
      loading.value.messageTypes = false
    }
  }
  
  async function fetchPerformance() {
    loading.value.performance = true
    try {
      const params = queryParams.value
      const url = `${API_BASE_URL}/api/metrics/performance?${params}`
      const response = await axios.get(url)
      performance.value = response.data
    } catch (error) {
      console.error('Failed to fetch performance:', error)
    } finally {
      loading.value.performance = false
    }
  }
  
  async function fetchErrors() {
    loading.value.errors = true
    try {
      const params = new URLSearchParams()
      if (timeRange.value.startTime) {
        params.append('start_time', timeRange.value.startTime)
      }
      if (timeRange.value.endTime) {
        params.append('end_time', timeRange.value.endTime)
      }
      params.append('interval_minutes', timeRange.value.intervalMinutes)
      const url = `${API_BASE_URL}/api/metrics/errors?${params.toString()}`
      const response = await axios.get(url)
      errors.value = response.data
    } catch (error) {
      console.error('Failed to fetch errors:', error)
    } finally {
      loading.value.errors = false
    }
  }
  
  async function fetchAllMetrics() {
    // Fetch each metric independently to avoid blocking
    // Don't await so they load in parallel but independently
    fetchTimeseries()
    fetchTransportDistribution()
    fetchMessageTypes()
    fetchMethods()
    fetchPerformance()
    fetchErrors()
  }
  
  function setTimeRange(start, end) {
    timeRange.value.startTime = start
    timeRange.value.endTime = end
    fetchAllMetrics()
  }
  
  function setIntervalMinutes(minutes) {
    timeRange.value.intervalMinutes = minutes
    fetchTimeseries()
    fetchErrors()
  }
  
  return {
    // State
    timeRange,
    timeseries,
    methods,
    transportDistribution,
    messageTypes,
    performance,
    errors,
    loading,
    
    // Computed
    filters,
    
    // Actions
    fetchTimeseries,
    fetchMethods,
    fetchTransportDistribution,
    fetchMessageTypes,
    fetchPerformance,
    fetchErrors,
    fetchAllMetrics,
    setTimeRange,
    setIntervalMinutes
  }
})