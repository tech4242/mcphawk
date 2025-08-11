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
        <Listbox v-model="selectedServers" multiple>
          <div class="relative">
            <ListboxButton
              class="relative w-full cursor-pointer rounded-lg bg-white dark:bg-gray-700 py-2 pl-3 pr-10 text-left shadow-md focus:outline-none focus-visible:border-mcp-blue focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-opacity-75 focus-visible:ring-offset-2 focus-visible:ring-offset-mcp-blue-light sm:text-sm"
            >
              <span class="block truncate text-gray-900 dark:text-gray-100">
                {{ selectedServersDisplay }}
              </span>
              <span class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                <ChevronUpDownIcon class="h-5 w-5 text-gray-400" aria-hidden="true" />
              </span>
            </ListboxButton>

            <transition
              leave-active-class="transition duration-100 ease-in"
              leave-from-class="opacity-100"
              leave-to-class="opacity-0"
            >
              <ListboxOptions
                class="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white dark:bg-gray-700 py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm"
              >
                <ListboxOption
                  key="all"
                  :value="'all'"
                  v-slot="{ active, selected }"
                  as="template"
                >
                  <li
                    :class="[
                      active ? 'bg-mcp-blue/10 dark:bg-mcp-blue/20 text-mcp-blue' : 'text-gray-900 dark:text-gray-100',
                      'relative cursor-pointer select-none py-2 pl-10 pr-4',
                    ]"
                    @click="handleAllServersClick"
                  >
                    <span :class="[selectedServers.includes('all') ? 'font-medium' : 'font-normal', 'block truncate']">
                      All Servers
                    </span>
                    <span v-if="selectedServers.includes('all')" class="absolute inset-y-0 left-0 flex items-center pl-3 text-mcp-blue">
                      <CheckIcon class="h-5 w-5" aria-hidden="true" />
                    </span>
                  </li>
                </ListboxOption>

                <ListboxOption
                  v-for="server in logStore.uniqueServers"
                  :key="server"
                  :value="server"
                  v-slot="{ active, selected }"
                  as="template"
                >
                  <li
                    :class="[
                      active ? 'bg-mcp-blue/10 dark:bg-mcp-blue/20 text-mcp-blue' : 'text-gray-900 dark:text-gray-100',
                      'relative cursor-pointer select-none py-2 pl-10 pr-4',
                    ]"
                  >
                    <span :class="[selectedServers.includes(server) ? 'font-medium' : 'font-normal', 'block truncate']">
                      {{ server }}
                    </span>
                    <span v-if="selectedServers.includes(server)" class="absolute inset-y-0 left-0 flex items-center pl-3 text-mcp-blue">
                      <CheckIcon class="h-5 w-5" aria-hidden="true" />
                    </span>
                  </li>
                </ListboxOption>
              </ListboxOptions>
            </transition>
          </div>
        </Listbox>
      </div>

      <!-- Time Range Section (Analytics only) -->
      <div v-if="isAnalyticsView">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Time Range</h3>
        <div class="space-y-3">
          <!-- Quick Range Buttons -->
          <div class="flex flex-wrap gap-2">
            <button
              v-for="range in quickRanges"
              :key="range.label"
              @click="selectQuickRange(range)"
              :class="[
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
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
        <Listbox v-model="selectedMessageTypes" multiple>
          <div class="relative">
            <ListboxButton
              class="relative w-full cursor-pointer rounded-lg bg-white dark:bg-gray-700 py-2 pl-3 pr-10 text-left shadow-md focus:outline-none focus-visible:border-mcp-blue focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-opacity-75 focus-visible:ring-offset-2 focus-visible:ring-offset-mcp-blue-light sm:text-sm"
            >
              <span class="block truncate text-gray-900 dark:text-gray-100">
                {{ selectedMessageTypesDisplay }}
              </span>
              <span class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                <ChevronUpDownIcon class="h-5 w-5 text-gray-400" aria-hidden="true" />
              </span>
            </ListboxButton>

            <transition
              leave-active-class="transition duration-100 ease-in"
              leave-from-class="opacity-100"
              leave-to-class="opacity-0"
            >
              <ListboxOptions
                class="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white dark:bg-gray-700 py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm"
              >
                <ListboxOption
                  v-for="filterOption in typeFilters"
                  :key="filterOption.value"
                  :value="filterOption.value"
                  v-slot="{ active, selected }"
                  as="template"
                >
                  <li
                    :class="[
                      active ? 'bg-mcp-blue/10 dark:bg-mcp-blue/20 text-mcp-blue' : 'text-gray-900 dark:text-gray-100',
                      'relative cursor-pointer select-none py-2 pl-10 pr-4',
                    ]"
                    @click="filterOption.value === 'all' ? handleAllMessageTypesClick() : null"
                  >
                    <div class="flex items-center justify-between">
                      <span :class="[selectedMessageTypes.includes(filterOption.value) ? 'font-medium' : 'font-normal', 'block truncate']">
                        {{ filterOption.label }}
                      </span>
                      <span class="text-sm text-gray-500 dark:text-gray-400">
                        {{ formatCount(filterOption.count) }}
                      </span>
                    </div>
                    <span v-if="selectedMessageTypes.includes(filterOption.value)" class="absolute inset-y-0 left-0 flex items-center pl-3 text-mcp-blue">
                      <CheckIcon class="h-5 w-5" aria-hidden="true" />
                    </span>
                  </li>
                </ListboxOption>
              </ListboxOptions>
            </transition>
          </div>
        </Listbox>
      </div>

      <!-- Transport Type Section -->
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Transport Type</h3>
        <Listbox v-model="selectedTransport" multiple>
          <div class="relative">
            <ListboxButton
              class="relative w-full cursor-pointer rounded-lg bg-white dark:bg-gray-700 py-2 pl-3 pr-10 text-left shadow-md focus:outline-none focus-visible:border-mcp-blue focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-opacity-75 focus-visible:ring-offset-2 focus-visible:ring-offset-mcp-blue-light sm:text-sm"
            >
              <span class="block truncate text-gray-900 dark:text-gray-100">
                {{ selectedTransportDisplay }}
              </span>
              <span class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                <ChevronUpDownIcon class="h-5 w-5 text-gray-400" aria-hidden="true" />
              </span>
            </ListboxButton>

            <transition
              leave-active-class="transition duration-100 ease-in"
              leave-from-class="opacity-100"
              leave-to-class="opacity-0"
            >
              <ListboxOptions
                class="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white dark:bg-gray-700 py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm"
              >
                <ListboxOption
                  v-for="transport in transportOptions"
                  :key="transport.value"
                  :value="transport.value"
                  v-slot="{ active, selected }"
                  as="template"
                >
                  <li
                    :class="[
                      active ? 'bg-mcp-blue/10 dark:bg-mcp-blue/20 text-mcp-blue' : 'text-gray-900 dark:text-gray-100',
                      'relative cursor-pointer select-none py-2 pl-10 pr-4',
                    ]"
                    @click="transport.value === 'all' ? handleAllTransportsClick() : null"
                  >
                    <span :class="[selectedTransport.includes(transport.value) ? 'font-medium' : 'font-normal', 'block truncate']">
                      {{ transport.label }}
                    </span>
                    <span v-if="selectedTransport.includes(transport.value)" class="absolute inset-y-0 left-0 flex items-center pl-3 text-mcp-blue">
                      <CheckIcon class="h-5 w-5" aria-hidden="true" />
                    </span>
                  </li>
                </ListboxOption>
              </ListboxOptions>
            </transition>
          </div>
        </Listbox>
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
        v-if="!isAnalyticsView"
        @click="logStore.fetchLogs()"
        class="w-full px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
      >
        <ArrowPathIcon class="h-4 w-4" :class="{ 'animate-spin': logStore.loading }" />
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
import { ArrowPathIcon, XMarkIcon, CalendarDaysIcon, ClockIcon, ChevronUpDownIcon, CheckIcon } from '@heroicons/vue/24/outline'
import { Listbox, ListboxButton, ListboxOptions, ListboxOption } from '@headlessui/vue'
import VueDatePicker from '@vuepic/vue-datepicker'
import '@vuepic/vue-datepicker/dist/main.css'
import dayjs from 'dayjs'

const logStore = useLogStore()
const analyticsStore = useAnalyticsStore()
const route = useRoute()

const selectedMessageTypes = ref(['all'])
const selectedTransport = ref(['all'])
const selectedServers = ref(['all'])

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
    if (!logStore.filter.includes('all') && logStore.filter.length > 0) count++
    if (!logStore.transportFilter.includes('all') && logStore.transportFilter.length > 0) count++
    if (!logStore.serverFilter.includes('all') && logStore.serverFilter.length > 0) count++
    if (logStore.searchQuery) count++
  } else {
    if (!logStore.transportFilter.includes('all') && logStore.transportFilter.length > 0) count++
    if (!logStore.serverFilter.includes('all') && logStore.serverFilter.length > 0) count++
    // Add time range as an active filter
    if (selectedRange.value !== 'All Data') count++
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
  
  // Add time range filter for analytics view
  if (isAnalyticsView.value && selectedRange.value && selectedRange.value !== 'All Data') {
    filters.push({
      key: 'timeRange',
      type: 'timeRange',
      value: selectedRange.value,
      label: `Time: ${selectedRange.value}`
    })
  }
  
  if (!logStore.filter.includes('all') && logStore.filter.length > 0) {
    const typeLabel = logStore.filter.length === 1 
      ? typeFilters.value.find(f => f.value === logStore.filter[0])?.label || logStore.filter[0]
      : `${logStore.filter.length} message types`
    filters.push({
      key: 'type',
      type: 'type',
      value: logStore.filter,
      label: typeLabel
    })
  }
  
  if (!logStore.transportFilter.includes('all') && logStore.transportFilter.length > 0) {
    const transportLabel = logStore.transportFilter.length === 1 
      ? transportOptions.find(t => t.value === logStore.transportFilter[0])?.label || logStore.transportFilter[0]
      : `${logStore.transportFilter.length} transports`
    filters.push({
      key: 'transport',
      type: 'transport',
      value: logStore.transportFilter,
      label: transportLabel
    })
  }
  
  if (!logStore.serverFilter.includes('all') && logStore.serverFilter.length > 0) {
    const serverLabel = logStore.serverFilter.length === 1 
      ? `Server: ${logStore.serverFilter[0]}`
      : `Servers: ${logStore.serverFilter.length} selected`
    filters.push({
      key: 'server',
      type: 'server',
      value: logStore.serverFilter,
      label: serverLabel
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

function removeFilter(filter) {
  switch (filter.type) {
    case 'type':
      selectedMessageTypes.value = ['all']
      logStore.setFilter(['all'])
      break
    case 'transport':
      selectedTransport.value = ['all']
      logStore.setTransportFilter(['all'])
      break
    case 'server':
      selectedServers.value = ['all']
      logStore.setServerFilter(['all'])
      break
    case 'search':
      logStore.setSearchQuery('')
      break
    case 'timeRange':
      // Reset to All Data
      selectQuickRange({ label: 'All Data', special: 'all' })
      break
  }
}

function clearAllFilters() {
  selectedMessageTypes.value = ['all']
  logStore.setFilter(['all'])
  selectedTransport.value = ['all']
  logStore.setTransportFilter(['all'])
  selectedServers.value = ['all']
  logStore.setServerFilter(['all'])
  logStore.setSearchQuery('')
  if (isAnalyticsView.value) {
    selectQuickRange({ label: 'All Data', special: 'all' })
  }
}

// Sync with store
watch(() => logStore.filter, (value) => {
  if (Array.isArray(value)) {
    selectedMessageTypes.value = value
  } else {
    // Handle backward compatibility
    selectedMessageTypes.value = value === 'all' ? ['all'] : [value]
  }
})

watch(() => logStore.transportFilter, (value) => {
  if (Array.isArray(value)) {
    selectedTransport.value = value
  } else {
    // Handle backward compatibility
    selectedTransport.value = value === 'all' ? ['all'] : [value]
  }
  // Refresh analytics when filter changes
  if (isAnalyticsView.value) {
    analyticsStore.fetchAllMetrics()
  }
})

watch(() => logStore.serverFilter, (value) => {
  if (Array.isArray(value)) {
    selectedServers.value = value
  } else {
    // Handle backward compatibility
    selectedServers.value = value === 'all' ? ['all'] : [value]
  }
  // Refresh analytics when filter changes
  if (isAnalyticsView.value) {
    analyticsStore.fetchAllMetrics()
  }
})

// Computed properties for multi-select displays
const selectedMessageTypesDisplay = computed(() => {
  if (selectedMessageTypes.value.includes('all')) {
    return 'All Messages'
  } else if (selectedMessageTypes.value.length === 0) {
    return 'Select types...'
  } else if (selectedMessageTypes.value.length === 1) {
    const typeFilter = typeFilters.value.find(f => f.value === selectedMessageTypes.value[0])
    return typeFilter ? typeFilter.label : selectedMessageTypes.value[0]
  } else {
    return `${selectedMessageTypes.value.length} types selected`
  }
})

const selectedTransportDisplay = computed(() => {
  if (selectedTransport.value.includes('all')) {
    return 'All Transports'
  } else if (selectedTransport.value.length === 0) {
    return 'Select transports...'
  } else if (selectedTransport.value.length === 1) {
    const transport = transportOptions.find(t => t.value === selectedTransport.value[0])
    return transport ? transport.label : selectedTransport.value[0]
  } else {
    return `${selectedTransport.value.length} transports selected`
  }
})

const selectedServersDisplay = computed(() => {
  if (selectedServers.value.includes('all')) {
    return 'All Servers'
  } else if (selectedServers.value.length === 0) {
    return 'Select servers...'
  } else if (selectedServers.value.length === 1) {
    return selectedServers.value[0]
  } else {
    return `${selectedServers.value.length} servers selected`
  }
})

// Handle "All" click for multi-select dropdowns
function handleAllMessageTypesClick() {
  if (selectedMessageTypes.value.includes('all')) {
    // If "all" is already selected, deselect it
    selectedMessageTypes.value = []
  } else {
    // Select only "all" and deselect everything else
    selectedMessageTypes.value = ['all']
  }
}

function handleAllTransportsClick() {
  if (selectedTransport.value.includes('all')) {
    // If "all" is already selected, deselect it
    selectedTransport.value = []
  } else {
    // Select only "all" and deselect everything else
    selectedTransport.value = ['all']
  }
}

function handleAllServersClick() {
  if (selectedServers.value.includes('all')) {
    // If "all" is already selected, deselect it
    selectedServers.value = []
  } else {
    // Select only "all" and deselect everything else
    selectedServers.value = ['all']
  }
}

// Watch multi-select arrays for changes
watch(selectedMessageTypes, (newValue, oldValue) => {
  // If user selects a specific type while "all" is selected, remove "all"
  if (newValue.includes('all') && newValue.length > 1) {
    // Check if "all" was already selected
    if (oldValue && oldValue.includes('all')) {
      // Remove "all" since user selected a specific type
      selectedMessageTypes.value = newValue.filter(t => t !== 'all')
    } else {
      // User selected "all", so clear other selections
      selectedMessageTypes.value = ['all']
    }
  }
  
  // Update the store
  logStore.setFilter(selectedMessageTypes.value)
})

watch(selectedTransport, (newValue, oldValue) => {
  // If user selects a specific transport while "all" is selected, remove "all"
  if (newValue.includes('all') && newValue.length > 1) {
    // Check if "all" was already selected
    if (oldValue && oldValue.includes('all')) {
      // Remove "all" since user selected a specific transport
      selectedTransport.value = newValue.filter(t => t !== 'all')
    } else {
      // User selected "all", so clear other selections
      selectedTransport.value = ['all']
    }
  }
  
  // Update the store
  logStore.setTransportFilter(selectedTransport.value)
})

watch(selectedServers, (newValue, oldValue) => {
  // If user selects a specific server while "all" is selected, remove "all"
  if (newValue.includes('all') && newValue.length > 1) {
    // Check if "all" was already selected
    if (oldValue && oldValue.includes('all')) {
      // Remove "all" since user selected a specific server
      selectedServers.value = newValue.filter(s => s !== 'all')
    } else {
      // User selected "all", so clear other selections
      selectedServers.value = ['all']
    }
  }
  
  // Update the store
  logStore.setServerFilter(selectedServers.value)
})

// Initialize time range for analytics on mount
onMounted(() => {
  if (isAnalyticsView.value) {
    // Set initial date range for analytics to Last 24 Hours
    selectQuickRange({ label: 'Last 24 Hours', hours: 24 })
  }
  
  // Initialize multi-select values from store
  if (Array.isArray(logStore.filter)) {
    selectedMessageTypes.value = logStore.filter
  } else {
    selectedMessageTypes.value = logStore.filter === 'all' ? ['all'] : [logStore.filter]
  }
  
  if (Array.isArray(logStore.transportFilter)) {
    selectedTransport.value = logStore.transportFilter
  } else {
    selectedTransport.value = logStore.transportFilter === 'all' ? ['all'] : [logStore.transportFilter]
  }
  
  if (Array.isArray(logStore.serverFilter)) {
    selectedServers.value = logStore.serverFilter
  } else {
    selectedServers.value = logStore.serverFilter === 'all' ? ['all'] : [logStore.serverFilter]
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