<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <!-- Header -->
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
      <div class="px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center">
            <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
              🦅 MCPHawk
            </h1>
            <ConnectionStatus class="ml-4" />
          </div>
          <div class="flex items-center space-x-4">
            <StatsPanel />
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1">
      <div class="px-4 sm:px-6 lg:px-8 py-4">
        <!-- Filters -->
        <div class="mb-4">
          <LogFilters />
        </div>

        <!-- Log Table -->
        <div class="bg-white dark:bg-gray-800 shadow rounded-lg">
          <LogTable />
        </div>
      </div>
    </main>

    <!-- Message Detail Modal -->
    <MessageDetailModal />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useLogStore } from '@/stores/logs'
import { useWebSocketStore } from '@/stores/websocket'
import ConnectionStatus from '@/components/common/ConnectionStatus.vue'
import ThemeToggle from '@/components/common/ThemeToggle.vue'
import StatsPanel from '@/components/Stats/StatsPanel.vue'
import LogFilters from '@/components/LogTable/LogFilters.vue'
import LogTable from '@/components/LogTable/LogTable.vue'
import MessageDetailModal from '@/components/MessageDetail/MessageDetailModal.vue'

const logStore = useLogStore()
const wsStore = useWebSocketStore()

onMounted(() => {
  // Load initial logs
  logStore.fetchLogs()
  
  // Connect WebSocket
  wsStore.connect()
})

onUnmounted(() => {
  wsStore.disconnect()
})
</script>