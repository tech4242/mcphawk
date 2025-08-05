<template>
  <div class="relative">
    <!-- Loading overlay -->
    <div v-if="logStore.loading" class="absolute inset-0 bg-white/50 dark:bg-gray-800/50 flex items-center justify-center z-10">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-mcp-blue"></div>
    </div>

    <!-- Table -->
    <div class="overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700 table-fixed">
        <thead class="bg-gray-50 dark:bg-gray-700/50">
          <tr>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider w-20">
              Date
            </th>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider w-24">
              Time
            </th>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider w-24">
              Type
            </th>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider w-16">
              ID
            </th>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider">
              Message
            </th>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider w-32">
              Server
            </th>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider w-28">
              Transport
            </th>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider w-40">
              Source → Dest
            </th>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider w-20">
              Port
            </th>
            <th class="px-3 py-4 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider w-16">
              PID
            </th>
          </tr>
        </thead>
        <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
          <LogRow
            v-for="log in displayLogs"
            :key="log.log_id"
            :log="log"
            :all-logs="logStore.logs"
            :is-selected="logStore.selectedLogId === log.log_id"
            :is-expanded="logStore.expandAll"
            @click="handleLogClick(log)"
          />
          
          <!-- Empty state -->
          <tr v-if="!logStore.loading && displayLogs.length === 0">
            <td colspan="10" class="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
              <div class="flex flex-col items-center">
                <svg class="w-12 h-12 mb-4 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p class="text-lg font-medium">No logs captured yet</p>
                <p class="text-sm mt-1">MCP traffic will appear here when detected</p>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Virtual scrolling for large datasets would go here -->
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useLogStore } from '@/stores/logs'
import LogRow from './LogRow.vue'

const logStore = useLogStore()

// For now, just show filtered logs. Later we'll add virtual scrolling
const displayLogs = computed(() => logStore.filteredLogs)

function handleLogClick(log) {
  logStore.selectLog(log.log_id)
}
</script>