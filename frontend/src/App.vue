<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
    <!-- Header -->
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 z-10">
      <div class="px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center space-x-4">
            <img src="/mcphawk_logo.png" alt="MCPHawk Logo" class="h-[62px]">
            <ConnectionStatus />
            <div class="h-8 w-px bg-gray-300 dark:bg-gray-600"></div>
            
            <!-- Navigation Tabs -->
            <nav class="flex space-x-1">
              <RouterLink
                to="/"
                v-slot="{ isActive }"
                custom
              >
                <button
                  @click="$router.push('/')"
                  :class="[
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                      : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700'
                  ]"
                >
                  <div class="flex items-center gap-2">
                    <TableCellsIcon class="h-4 w-4" />
                    <span>Logs</span>
                  </div>
                </button>
              </RouterLink>
              
              <RouterLink
                to="/analytics"
                v-slot="{ isActive }"
                custom
              >
                <button
                  @click="$router.push('/analytics')"
                  :class="[
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                      : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700'
                  ]"
                >
                  <div class="flex items-center gap-2">
                    <ChartBarIcon class="h-4 w-4" />
                    <span>Analytics</span>
                  </div>
                </button>
              </RouterLink>
            </nav>
          </div>
          <div class="flex items-center space-x-4">
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>

    <!-- Router View -->
    <RouterView />

    <!-- Message Detail Modal -->
    <MessageDetailModal />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, provide, ref } from 'vue'
import { RouterView, RouterLink } from 'vue-router'
import { useLogStore } from '@/stores/logs'
import { useWebSocketStore } from '@/stores/websocket'
import ConnectionStatus from '@/components/common/ConnectionStatus.vue'
import ThemeToggle from '@/components/common/ThemeToggle.vue'
import MessageDetailModal from '@/components/MessageDetail/MessageDetailModal.vue'
import { ViewColumnsIcon, TableCellsIcon, ChartBarIcon } from '@heroicons/vue/24/outline'

const logStore = useLogStore()
const wsStore = useWebSocketStore()
const sidebarOpen = ref(true) // Default to open on desktop

// Provide sidebar state to child components
provide('sidebarOpen', sidebarOpen)

// Toggle sidebar
const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

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