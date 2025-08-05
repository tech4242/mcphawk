<template>
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

      <!-- Clear Display -->
      <button
        @click="handleClearLogs"
        class="p-2.5 rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-red-100 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200"
        title="Clear display"
      >
        <TrashIcon class="h-5 w-5" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useLogStore } from '@/stores/logs'
import {
  MagnifyingGlassIcon,
  XMarkIcon,
  CodeBracketIcon,
  TrashIcon
} from '@heroicons/vue/24/outline'

const logStore = useLogStore()
const searchQuery = ref('')

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
    logStore.setTransportFilter(transportMatch[1])
    searchQuery.value = query.replace(transportMatch[0], '').trim()
  }
  
  if (serverMatch) {
    logStore.setServerFilter(serverMatch[1])
    searchQuery.value = query.replace(serverMatch[0], '').trim()
  }
}

function clearSearch() {
  searchQuery.value = ''
  logStore.setSearchQuery('')
}

function handleClearLogs() {
  if (confirm('Are you sure you want to clear all logs from the display? This will not delete logs from the database.')) {
    logStore.clearLogs()
  }
}
</script>