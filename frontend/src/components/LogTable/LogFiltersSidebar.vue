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
      <!-- Message Type Section -->
      <div>
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

      <!-- Server Section -->
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

      <!-- Additional Options -->
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Display Options</h3>
        <div class="space-y-3">
          <label class="flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200">
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">Expand all JSON</span>
            <button
              @click.stop="logStore.toggleExpandAll"
              class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
              :class="logStore.expandAll ? 'bg-mcp-blue' : 'bg-gray-300 dark:bg-gray-600'"
            >
              <span
                class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                :class="logStore.expandAll ? 'translate-x-6' : 'translate-x-1'"
              />
            </button>
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
import { computed, ref, watch } from 'vue'
import { useLogStore } from '@/stores/logs'
import { ArrowPathIcon, XMarkIcon } from '@heroicons/vue/24/outline'

const logStore = useLogStore()

const selectedTransport = ref('all')
const selectedServer = ref('all')

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
  if (logStore.filter !== 'all') count++
  if (logStore.transportFilter !== 'all') count++
  if (logStore.serverFilter !== 'all') count++
  if (logStore.searchQuery) count++
  return count
})

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
</script>