<template>
  <div class="h-full bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
    <!-- Sidebar Header -->
    <div class="p-4 border-b border-gray-200 dark:border-gray-700">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">Filters</h2>
      <div v-if="activeFilters.length > 0" class="flex flex-wrap gap-2">
        <span
          v-for="filter in activeFilters"
          :key="filter.key"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-mcp-blue/10 text-mcp-blue dark:bg-mcp-blue/20 dark:text-mcp-blue-light border border-mcp-blue/20"
        >
          {{ filter.label }}
          <button
            @click="removeFilter(filter)"
            class="ml-0.5 hover:text-mcp-blue-dark dark:hover:text-white transition-colors"
          >
            <XMarkIcon class="h-3.5 w-3.5" />
          </button>
        </span>
      </div>
      <p v-else class="text-sm text-gray-500 dark:text-gray-400">
        No active filters
      </p>
    </div>

    <!-- Sidebar Content -->
    <div class="flex-1 overflow-y-auto p-4 space-y-6">
      <!-- Server Section (Always shown, at top) -->
      <div v-if="logStore.uniqueServers.length > 0">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Server</h3>
        <div class="space-y-2">
          <label
            class="flex items-center p-3 rounded-lg cursor-pointer transition-all duration-200"
            :class="[
              selectedServer === 'all'
                ? 'bg-mcp-blue/10 dark:bg-mcp-blue/20 border border-mcp-blue/30'
                : 'bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 border border-transparent'
            ]"
          >
            <input
              type="radio"
              name="server"
              value="all"
              :checked="selectedServer === 'all'"
              @change="updateServer('all')"
              class="sr-only"
            >
            <div class="flex items-center flex-1">
              <div
                class="w-4 h-4 rounded-full border-2 mr-3 flex items-center justify-center"
                :class="[
                  selectedServer === 'all'
                    ? 'border-mcp-blue bg-mcp-blue'
                    : 'border-gray-400 dark:border-gray-500'
                ]"
              >
                <div
                  v-if="selectedServer === 'all'"
                  class="w-2 h-2 rounded-full bg-white"
                ></div>
              </div>
              <span
                class="text-sm font-medium"
                :class="[
                  selectedServer === 'all'
                    ? 'text-mcp-blue dark:text-mcp-blue-light'
                    : 'text-gray-700 dark:text-gray-300'
                ]"
              >
                All Servers
              </span>
            </div>
          </label>
          <label
            v-for="server in logStore.uniqueServers"
            :key="server"
            class="flex items-center p-3 rounded-lg cursor-pointer transition-all duration-200"
            :class="[
              selectedServer === server
                ? 'bg-mcp-blue/10 dark:bg-mcp-blue/20 border border-mcp-blue/30'
                : 'bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 border border-transparent'
            ]"
          >
            <input
              type="radio"
              name="server"
              :value="server"
              :checked="selectedServer === server"
              @change="updateServer(server)"
              class="sr-only"
            >
            <div class="flex items-center flex-1">
              <div
                class="w-4 h-4 rounded-full border-2 mr-3 flex items-center justify-center"
                :class="[
                  selectedServer === server
                    ? 'border-mcp-blue bg-mcp-blue'
                    : 'border-gray-400 dark:border-gray-500'
                ]"
              >
                <div
                  v-if="selectedServer === server"
                  class="w-2 h-2 rounded-full bg-white"
                ></div>
              </div>
              <span
                class="text-sm font-medium truncate"
                :class="[
                  selectedServer === server
                    ? 'text-mcp-blue dark:text-mcp-blue-light'
                    : 'text-gray-700 dark:text-gray-300'
                ]"
                :title="server"
              >
                {{ server }}
              </span>
            </div>
          </label>
        </div>
      </div>

      <!-- Time Range Section (Analytics only) -->
      <div v-if="isAnalyticsView">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Time Range</h3>
        <div class="space-y-3">
          <!-- Quick Range Buttons -->
          <div class="grid grid-cols-2 gap-2">
            <button
              v-for="range in quickRanges"
              :key="range.label"
              @click="selectQuickRange(range)"
              :class="[
                'px-2 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
                selectedRange === range.label
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700'
              ]"
            >
              {{ range.label }}
            </button>
          </div>
          
          <!-- Custom Date Range -->
          <div>
            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Custom Range:</label>
            <VueDatePicker
              v-model="dateRange"
              range
              :enable-time-picker="false"
              :dark="isDark"
              :format="dateFormat"
              :preview-format="dateFormat"
              placeholder="Select dates"
              @update:model-value="onDateRangeChange"
              class="w-full"
            />
          </div>
          
          <!-- Interval Selector -->
          <div>
            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Interval:</label>
            <select
              v-model="intervalMinutes"
              @change="onIntervalChange"
              class="w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option :value="1">1 minute</option>
              <option :value="5">5 minutes</option>
              <option :value="10">10 minutes</option>
              <option :value="15">15 minutes</option>
              <option :value="30">30 minutes</option>
              <option :value="60">1 hour</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Message Type Section (Logs only) -->
      <div v-if="!isAnalyticsView">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Message Type</h3>
        <div class="space-y-2">
          <label
            v-for="filterOption in typeFilters"
            :key="filterOption.value"
            class="flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all duration-200"
            :class="[
              logStore.filter === filterOption.value
                ? 'bg-mcp-blue/10 dark:bg-mcp-blue/20 border border-mcp-blue/30'
                : 'bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 border border-transparent'
            ]"
          >
            <div class="flex items-center">
              <input
                type="radio"
                :name="'message-type'"
                :value="filterOption.value"
                :checked="logStore.filter === filterOption.value"
                @change="logStore.setFilter(filterOption.value)"
                class="sr-only"
              >
              <div class="flex items-center">
                <div
                  class="w-4 h-4 rounded-full border-2 mr-3 flex items-center justify-center"
                  :class="[
                    logStore.filter === filterOption.value
                      ? 'border-mcp-blue bg-mcp-blue'
                      : 'border-gray-400 dark:border-gray-500'
                  ]"
                >
                  <div
                    v-if="logStore.filter === filterOption.value"
                    class="w-2 h-2 rounded-full bg-white"
                  ></div>
                </div>
                <span
                  class="text-sm font-medium"
                  :class="[
                    logStore.filter === filterOption.value
                      ? 'text-mcp-blue dark:text-mcp-blue-light'
                      : 'text-gray-700 dark:text-gray-300'
                  ]"
                >
                  {{ filterOption.label }}
                </span>
              </div>
            </div>
            <span
              class="text-sm"
              :class="[
                logStore.filter === filterOption.value
                  ? 'text-mcp-blue dark:text-mcp-blue-light font-semibold'
                  : 'text-gray-500 dark:text-gray-400'
              ]"
            >
              {{ formatCount(filterOption.count) }}
            </span>
          </label>
        </div>
      </div>

      <!-- Transport Type Section -->
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Transport Type</h3>
        <div class="space-y-2">
          <label
            v-for="transport in transportOptions"
            :key="transport.value"
            class="flex items-center p-3 rounded-lg cursor-pointer transition-all duration-200"
            :class="[
              selectedTransport === transport.value
                ? 'bg-mcp-blue/10 dark:bg-mcp-blue/20 border border-mcp-blue/30'
                : 'bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 border border-transparent'
            ]"
          >
            <input
              type="radio"
              :name="'transport-type'"
              :value="transport.value"
              :checked="selectedTransport === transport.value"
              @change="updateTransport(transport.value)"
              class="sr-only"
            >
            <div class="flex items-center flex-1">
              <div
                class="w-4 h-4 rounded-full border-2 mr-3 flex items-center justify-center"
                :class="[
                  selectedTransport === transport.value
                    ? 'border-mcp-blue bg-mcp-blue'
                    : 'border-gray-400 dark:border-gray-500'
                ]"
              >
                <div
                  v-if="selectedTransport === transport.value"
                  class="w-2 h-2 rounded-full bg-white"
                ></div>
              </div>
              <span
                class="text-sm font-medium"
                :class="[
                  selectedTransport === transport.value
                    ? 'text-mcp-blue dark:text-mcp-blue-light'
                    : 'text-gray-700 dark:text-gray-300'
                ]"
              >
                {{ transport.label }}
              </span>
            </div>
          </label>
        </div>
      </div>
    </div>

    <!-- Sidebar Footer -->
    <div class="p-4 border-t border-gray-200 dark:border-gray-700 space-y-3">
      <button
        v-if="activeFilterCount > 0"
        @click="clearAllFilters"
        class="w-full px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-all duration-200"
      >
        Clear All Filters
      </button>
      <button
        @click="isAnalyticsView ? analyticsStore.fetchAllMetrics() : logStore.fetchLogs()"
        class="w-full px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
      >
        <ArrowPathIcon class="h-4 w-4" :class="{ 'animate-spin': isAnalyticsView ? Object.values(analyticsStore.loading).some(v => v) : logStore.loading }" />
        Refresh
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useLogStore } from '@/stores/logs'
import { useAnalyticsStore } from '@/stores/analytics'
import { ArrowPathIcon, XMarkIcon, CalendarDaysIcon, ClockIcon } from '@heroicons/vue/24/outline'
import VueDatePicker from '@vuepic/vue-datepicker'
import '@vuepic/vue-datepicker/dist/main.css'
import dayjs from 'dayjs'

const logStore = useLogStore()
const analyticsStore = useAnalyticsStore()
const route = useRoute()

const selectedTransport = ref('all')
const selectedServer = ref('all')

// Time range state for analytics
const dateRange = ref([])
const selectedRange = ref('Last Hour')
const intervalMinutes = ref(5)

// Computed properties
const isAnalyticsView = computed(() => route.name === 'analytics')
const isDark = computed(() => document.documentElement.classList.contains('dark'))

const typeFilters = computed(() => [
  { label: 'All Messages', value: 'all', count: logStore.stats.total },
  { label: 'Requests', value: 'request', count: logStore.stats.requests },
  { label: 'Responses', value: 'response', count: logStore.stats.responses },
  { label: 'Notifications', value: 'notification', count: logStore.stats.notifications },
  { label: 'Errors', value: 'error', count: logStore.stats.errors }
])

const transportOptions = [
  { label: 'All Transports', value: 'all' },
  { label: 'Streamable HTTP', value: 'streamable_http' },
  { label: 'HTTP+SSE', value: 'http_sse' },
  { label: 'stdio', value: 'stdio' },
  { label: 'Unknown', value: 'unknown' }
]

const activeFilterCount = computed(() => {
  let count = 0
  if (!isAnalyticsView.value) {
    if (logStore.filter !== 'all') count++
    if (logStore.transportFilter !== 'all') count++
    if (logStore.serverFilter !== 'all') count++
    if (logStore.searchQuery) count++
  } else {
    if (logStore.transportFilter !== 'all') count++
    if (logStore.serverFilter !== 'all') count++
  }
  return count
})

// Time range functions for analytics
const quickRanges = [
  { label: 'All Data', special: 'all' },
  { label: 'Last Hour', hours: 1 },
  { label: 'Last 6 Hours', hours: 6 },
  { label: 'Last 24 Hours', hours: 24 },
  { label: 'Last 7 Days', days: 7 },
  { label: 'Last 30 Days', days: 30 }
]

const dateFormat = (dates) => {
  if (!dates) return ''
  if (Array.isArray(dates)) {
    const start = dayjs(dates[0]).format('MMM D, YYYY')
    const end = dates[1] ? dayjs(dates[1]).format('MMM D, YYYY') : ''
    return end ? `${start} - ${end}` : start
  }
  return dayjs(dates).format('MMM D, YYYY')
}

function selectQuickRange(range) {
  selectedRange.value = range.label
  
  if (range.special === 'all') {
    dateRange.value = []
    analyticsStore.setTimeRange(null, null)
    return
  }
  
  const now = new Date()
  let start
  
  if (range.hours) {
    start = new Date(now.getTime() - range.hours * 60 * 60 * 1000)
  } else if (range.days) {
    start = new Date(now.getTime() - range.days * 24 * 60 * 60 * 1000)
  }
  
  dateRange.value = [start, now]
  updateTimeRange()
}

function onDateRangeChange() {
  selectedRange.value = null
  updateTimeRange()
}

function updateTimeRange() {
  if (dateRange.value && dateRange.value.length === 2) {
    const [start, end] = dateRange.value
    
    const rangeDays = dayjs(end).diff(dayjs(start), 'day')
    if (rangeDays > 30) {
      intervalMinutes.value = 60 * 24
    } else if (rangeDays > 7) {
      intervalMinutes.value = 60 * 6
    } else if (rangeDays > 2) {
      intervalMinutes.value = 60
    } else if (rangeDays > 0) {
      intervalMinutes.value = 15
    } else {
      intervalMinutes.value = 5
    }
    
    analyticsStore.setIntervalMinutes(intervalMinutes.value)
    analyticsStore.setTimeRange(
      start.toISOString(),
      end.toISOString()
    )
  }
}

function onIntervalChange() {
  analyticsStore.setIntervalMinutes(intervalMinutes.value)
}

const activeFilters = computed(() => {
  const filters = []
  
  if (logStore.filter !== 'all') {
    const typeFilter = typeFilters.value.find(f => f.value === logStore.filter)
    if (typeFilter) {
      filters.push({
        key: 'type',
        type: 'type',
        value: logStore.filter,
        label: typeFilter.label
      })
    }
  }
  
  if (logStore.transportFilter !== 'all') {
    const transport = transportOptions.find(t => t.value === logStore.transportFilter)
    filters.push({
      key: 'transport',
      type: 'transport',
      value: logStore.transportFilter,
      label: transport ? transport.label : logStore.transportFilter
    })
  }
  
  if (logStore.serverFilter !== 'all') {
    filters.push({
      key: 'server',
      type: 'server',
      value: logStore.serverFilter,
      label: `Server: ${logStore.serverFilter}`
    })
  }
  
  if (logStore.searchQuery) {
    filters.push({
      key: 'search',
      type: 'search',
      value: logStore.searchQuery,
      label: `"${logStore.searchQuery}"`
    })
  }
  
  return filters
})

function formatCount(count) {
  if (count > 999) {
    return `${(count / 1000).toFixed(1)}k`
  }
  return count
}

function updateTransport(value) {
  selectedTransport.value = value
  logStore.setTransportFilter(value)
}

function updateServer(value) {
  selectedServer.value = value
  logStore.setServerFilter(value)
}

function removeFilter(filter) {
  switch (filter.type) {
    case 'type':
      logStore.setFilter('all')
      break
    case 'transport':
      selectedTransport.value = 'all'
      logStore.setTransportFilter('all')
      break
    case 'server':
      selectedServer.value = 'all'
      logStore.setServerFilter('all')
      break
    case 'search':
      logStore.setSearchQuery('')
      break
  }
}

function clearAllFilters() {
  logStore.setFilter('all')
  selectedTransport.value = 'all'
  logStore.setTransportFilter('all')
  selectedServer.value = 'all'
  logStore.setServerFilter('all')
  logStore.setSearchQuery('')
}

// Sync with store
watch(() => logStore.transportFilter, (value) => {
  selectedTransport.value = value
})

watch(() => logStore.serverFilter, (value) => {
  selectedServer.value = value
})

// Initialize time range for analytics on mount
onMounted(() => {
  if (isAnalyticsView.value) {
    // Set initial date range for analytics
    dateRange.value = [new Date('2025-08-02'), new Date('2025-08-08')]
    updateTimeRange()
    intervalMinutes.value = analyticsStore.timeRange.intervalMinutes
    selectedRange.value = 'Custom Range'
  }
})
</script>

<style>
/* Custom styles for the date picker in dark mode */
.dp__theme_dark {
  --dp-background-color: rgb(31 41 55);
  --dp-text-color: rgb(209 213 219);
  --dp-hover-color: rgb(55 65 81);
  --dp-hover-text-color: #ffffff;
  --dp-hover-icon-color: #959595;
  --dp-primary-color: rgb(59 130 246);
  --dp-primary-text-color: #ffffff;
  --dp-secondary-color: rgb(107 114 128);
  --dp-border-color: rgb(75 85 99);
  --dp-menu-border-color: rgb(75 85 99);
  --dp-border-color-hover: rgb(107 114 128);
}
</style>