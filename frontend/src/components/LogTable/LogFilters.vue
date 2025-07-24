<template>
  <div class="flex flex-col sm:flex-row gap-4">
    <!-- Filter buttons -->
    <div class="flex flex-wrap gap-2">
      <button
        v-for="filterOption in filters"
        :key="filterOption.value"
        @click="logStore.setFilter(filterOption.value)"
        class="px-4 py-2 rounded-lg font-medium transition-colors"
        :class="[
          logStore.filter === filterOption.value
            ? 'bg-mcp-blue text-white'
            : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
        ]"
      >
        {{ filterOption.label }}
        <span v-if="filterOption.count !== undefined" class="ml-1">
          ({{ filterOption.count }})
        </span>
      </button>
    </div>

    <!-- Search and controls -->
    <div class="flex-1 flex gap-2">
      <!-- Search input -->
      <div class="flex-1 relative">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search messages..."
          class="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-mcp-blue focus:border-transparent"
        >
        <MagnifyingGlassIcon class="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
      </div>

      <!-- Expand all -->
      <button
        @click="logStore.toggleExpandAll"
        class="px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
        :class="[
          logStore.expandAll
            ? 'bg-mcp-blue text-white'
            : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
        ]"
        :title="logStore.expandAll ? 'Collapse all JSON' : 'Expand all JSON'"
      >
        <CodeBracketIcon class="h-5 w-5" />
        <span class="hidden sm:inline">{{ logStore.expandAll ? 'Collapse' : 'Expand' }}</span>
      </button>

      <!-- Clear logs -->
      <button
        @click="handleClearLogs"
        class="px-4 py-2 rounded-lg font-medium bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/30 transition-colors"
        title="Clear all logs"
      >
        <TrashIcon class="h-5 w-5" />
      </button>

      <!-- Refresh -->
      <button
        @click="logStore.fetchLogs()"
        class="px-4 py-2 rounded-lg font-medium bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
        title="Refresh logs"
      >
        <ArrowPathIcon class="h-5 w-5" :class="{ 'animate-spin': logStore.loading }" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useLogStore } from '@/stores/logs'
import { MagnifyingGlassIcon, TrashIcon, ArrowPathIcon, CodeBracketIcon } from '@heroicons/vue/24/outline'

const logStore = useLogStore()

const searchQuery = ref('')

const filters = computed(() => [
  { label: 'All', value: 'all', count: logStore.stats.total },
  { label: 'Requests', value: 'request', count: logStore.stats.requests },
  { label: 'Responses', value: 'response', count: logStore.stats.responses },
  { label: 'Notifications', value: 'notification', count: logStore.stats.notifications },
  { label: 'Errors', value: 'error', count: logStore.stats.errors }
])

// Debounce search
let searchTimeout = null
watch(searchQuery, (newValue) => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    logStore.setSearchQuery(newValue)
  }, 300)
})

function handleClearLogs() {
  if (confirm('Are you sure you want to clear all logs from the display? This will not delete logs from the database.')) {
    logStore.clearLogs()
  }
}
</script>