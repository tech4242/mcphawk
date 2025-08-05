<template>
  <div class="space-y-3">
    <!-- Primary Controls Row -->
    <div class="flex items-center gap-3">
      <!-- Search Bar -->
      <div class="flex-1 relative">
        <div class="relative">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search messages, methods, or use filters like type:request"
            class="w-full pl-10 pr-10 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-mcp-blue focus:border-transparent transition-all duration-200"
            @keydown.enter="handleSearch"
          >
          <MagnifyingGlassIcon class="absolute left-3 top-3 h-5 w-5 text-gray-400" />
          <button
            v-if="searchQuery"
            @click="clearSearch"
            class="absolute right-3 top-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <XMarkIcon class="h-5 w-5" />
          </button>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="flex items-center gap-2">
        <!-- Filter Toggle -->
        <button
          @click="showFilters = !showFilters"
          class="px-4 py-2.5 rounded-xl font-medium transition-all duration-200 flex items-center gap-2"
          :class="[
            hasActiveFilters || showFilters
              ? 'bg-mcp-blue text-white shadow-md'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
          ]"
        >
          <FunnelIcon class="h-5 w-5" />
          <span class="hidden sm:inline">Filters</span>
          <span v-if="activeFilterCount > 0" class="ml-1 px-2 py-0.5 text-xs bg-white/20 rounded-full">
            {{ activeFilterCount }}
          </span>
        </button>

        <!-- Expand/Collapse -->
        <button
          @click="logStore.toggleExpandAll"
          class="p-2.5 rounded-xl transition-all duration-200"
          :class="[
            logStore.expandAll
              ? 'bg-mcp-blue text-white'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
          ]"
          :title="logStore.expandAll ? 'Collapse all' : 'Expand all'"
        >
          <CodeBracketIcon class="h-5 w-5" />
        </button>

        <!-- More Actions Menu -->
        <Menu as="div" class="relative">
          <MenuButton class="p-2.5 rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-all duration-200">
            <EllipsisVerticalIcon class="h-5 w-5" />
          </MenuButton>
          <transition
            enter-active-class="transition duration-100 ease-out"
            enter-from-class="transform scale-95 opacity-0"
            enter-to-class="transform scale-100 opacity-100"
            leave-active-class="transition duration-75 ease-in"
            leave-from-class="transform scale-100 opacity-100"
            leave-to-class="transform scale-95 opacity-0"
          >
            <MenuItems class="absolute right-0 mt-2 w-48 origin-top-right rounded-xl bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-10">
              <div class="py-1">
                <MenuItem v-slot="{ active }">
                  <button
                    @click="logStore.fetchLogs()"
                    :class="[
                      active ? 'bg-gray-100 dark:bg-gray-700' : '',
                      'flex items-center gap-3 w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-300'
                    ]"
                  >
                    <ArrowPathIcon class="h-5 w-5" :class="{ 'animate-spin': logStore.loading }" />
                    Refresh Logs
                  </button>
                </MenuItem>
                <MenuItem v-slot="{ active }">
                  <button
                    @click="handleClearLogs"
                    :class="[
                      active ? 'bg-gray-100 dark:bg-gray-700' : '',
                      'flex items-center gap-3 w-full px-4 py-2 text-sm text-red-600 dark:text-red-400'
                    ]"
                  >
                    <TrashIcon class="h-5 w-5" />
                    Clear Display
                  </button>
                </MenuItem>
              </div>
            </MenuItems>
          </transition>
        </Menu>
      </div>
    </div>

    <!-- Active Filters Pills -->
    <div v-if="activeFilters.length > 0" class="flex flex-wrap items-center gap-2">
      <span class="text-sm text-gray-500 dark:text-gray-400">Active filters:</span>
      <TransitionGroup
        tag="div"
        class="flex flex-wrap gap-2"
        enter-active-class="transition-all duration-300"
        enter-from-class="opacity-0 scale-90"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition-all duration-200"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-90"
      >
        <span
          v-for="filter in activeFilters"
          :key="filter.key"
          class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-mcp-blue/10 text-mcp-blue dark:bg-mcp-blue/20 dark:text-mcp-blue-light"
        >
          {{ filter.label }}
          <button
            @click="removeFilter(filter)"
            class="ml-1 hover:text-mcp-blue-dark dark:hover:text-white"
          >
            <XMarkIcon class="h-4 w-4" />
          </button>
        </span>
      </TransitionGroup>
      <button
        @click="clearAllFilters"
        class="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
      >
        Clear all
      </button>
    </div>

    <!-- Expandable Filters Panel -->
    <Transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div v-if="showFilters" class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 space-y-3">
        <!-- Message Type Filter -->
        <div class="flex flex-wrap gap-2">
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300 w-full mb-1">Message Type</span>
          <button
            v-for="filterOption in typeFilters"
            :key="filterOption.value"
            @click="logStore.setFilter(filterOption.value)"
            class="px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200"
            :class="[
              logStore.filter === filterOption.value
                ? 'bg-mcp-blue text-white shadow-sm'
                : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 border border-gray-200 dark:border-gray-600'
            ]"
          >
            {{ filterOption.label }}
            <span v-if="filterOption.count !== undefined" class="ml-1 opacity-70">
              {{ formatCount(filterOption.count) }}
            </span>
          </button>
        </div>

        <!-- Transport and Server Filters -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- Transport Filter -->
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Transport Type
            </label>
            <select
              v-model="selectedTransport"
              @change="logStore.setTransportFilter(selectedTransport)"
              class="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm focus:ring-2 focus:ring-mcp-blue focus:border-transparent"
            >
              <option value="all">All Transports</option>
              <option value="streamable_http">Streamable HTTP</option>
              <option value="http_sse">HTTP+SSE</option>
              <option value="stdio">stdio</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>

          <!-- Server Filter -->
          <div v-if="logStore.uniqueServers.length > 0">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Server
            </label>
            <select
              v-model="selectedServer"
              @change="logStore.setServerFilter(selectedServer)"
              class="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm focus:ring-2 focus:ring-mcp-blue focus:border-transparent"
            >
              <option value="all">All Servers</option>
              <option v-for="server in logStore.uniqueServers" :key="server" :value="server">
                {{ server }}
              </option>
            </select>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useLogStore } from '@/stores/logs'
import { Menu, MenuButton, MenuItems, MenuItem } from '@headlessui/vue'
import {
  MagnifyingGlassIcon,
  XMarkIcon,
  FunnelIcon,
  CodeBracketIcon,
  EllipsisVerticalIcon,
  ArrowPathIcon,
  TrashIcon
} from '@heroicons/vue/24/outline'

const logStore = useLogStore()

const searchQuery = ref('')
const selectedTransport = ref('all')
const selectedServer = ref('all')
const showFilters = ref(false)

const typeFilters = computed(() => [
  { label: 'All', value: 'all', count: logStore.stats.total },
  { label: 'Requests', value: 'request', count: logStore.stats.requests },
  { label: 'Responses', value: 'response', count: logStore.stats.responses },
  { label: 'Notifications', value: 'notification', count: logStore.stats.notifications },
  { label: 'Errors', value: 'error', count: logStore.stats.errors }
])

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
    filters.push({
      key: 'transport',
      type: 'transport',
      value: logStore.transportFilter,
      label: `Transport: ${logStore.transportFilter.replace('_', ' ')}`
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
      label: `Search: "${logStore.searchQuery}"`
    })
  }
  
  return filters
})

const activeFilterCount = computed(() => activeFilters.value.length)
const hasActiveFilters = computed(() => activeFilterCount.value > 0)

// Format large numbers
function formatCount(count) {
  if (count > 999) {
    return `${(count / 1000).toFixed(1)}k`
  }
  return count
}

// Debounce search
let searchTimeout = null
watch(searchQuery, (newValue) => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    logStore.setSearchQuery(newValue)
  }, 300)
})

function handleSearch() {
  // Parse search query for special filters
  const query = searchQuery.value.toLowerCase()
  const typeMatch = query.match(/type:(\w+)/)
  const transportMatch = query.match(/transport:(\w+)/)
  const serverMatch = query.match(/server:(\w+)/)
  
  if (typeMatch) {
    logStore.setFilter(typeMatch[1])
    searchQuery.value = query.replace(typeMatch[0], '').trim()
  }
  
  if (transportMatch) {
    selectedTransport.value = transportMatch[1]
    logStore.setTransportFilter(transportMatch[1])
    searchQuery.value = query.replace(transportMatch[0], '').trim()
  }
  
  if (serverMatch) {
    selectedServer.value = serverMatch[1]
    logStore.setServerFilter(serverMatch[1])
    searchQuery.value = query.replace(serverMatch[0], '').trim()
  }
}

function clearSearch() {
  searchQuery.value = ''
  logStore.setSearchQuery('')
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
      clearSearch()
      break
  }
}

function clearAllFilters() {
  logStore.setFilter('all')
  selectedTransport.value = 'all'
  logStore.setTransportFilter('all')
  selectedServer.value = 'all'
  logStore.setServerFilter('all')
  clearSearch()
  showFilters.value = false
}

function handleClearLogs() {
  if (confirm('Are you sure you want to clear all logs from the display? This will not delete logs from the database.')) {
    logStore.clearLogs()
  }
}

// Auto-hide filters when all are cleared
watch(hasActiveFilters, (hasFilters) => {
  if (!hasFilters && showFilters.value) {
    setTimeout(() => {
      showFilters.value = false
    }, 300)
  }
})
</script>