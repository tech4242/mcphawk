<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
    <!-- Header -->
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 z-10">
      <div class="px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center">
            <button
              @click="sidebarOpen = !sidebarOpen"
              class="lg:hidden p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              <Bars3Icon v-if="!sidebarOpen" class="h-6 w-6" />
              <XMarkIcon v-else class="h-6 w-6" />
            </button>
            <img src="/mcphawk_logo.png" alt="MCPHawk Logo" class="h-[62px] ml-2 lg:ml-0">
            <ConnectionStatus class="ml-4" />
          </div>
          <div class="flex items-center space-x-4">
            <StatsPanel />
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content Area -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Sidebar -->
      <aside
        class="w-80 flex-shrink-0 overflow-hidden transition-all duration-300 lg:relative lg:translate-x-0"
        :class="[
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
          'fixed inset-y-0 left-0 z-40 lg:static lg:inset-auto'
        ]"
      >
        <div class="h-full" style="margin-top: 65px;" class="lg:mt-0">
          <LogFiltersSidebar />
        </div>
      </aside>

      <!-- Mobile sidebar backdrop -->
      <div
        v-if="sidebarOpen"
        @click="sidebarOpen = false"
        class="lg:hidden fixed inset-0 bg-black/50 z-30"
        style="margin-top: 65px;"
      ></div>

      <!-- Main Content -->
      <main class="flex-1 overflow-auto">
        <div class="px-4 sm:px-6 lg:px-8 py-6">
          <!-- Search Bar and Actions -->
          <div class="mb-6">
            <LogSearchBar />
          </div>

          <!-- Log Table -->
          <div class="bg-white dark:bg-gray-800 shadow-xl rounded-xl overflow-hidden">
            <LogTable />
          </div>
        </div>
      </main>
    </div>

    <!-- Message Detail Modal -->
    <MessageDetailModal />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useLogStore } from '@/stores/logs'
import { useWebSocketStore } from '@/stores/websocket'
import ConnectionStatus from '@/components/common/ConnectionStatus.vue'
import ThemeToggle from '@/components/common/ThemeToggle.vue'
import StatsPanel from '@/components/Stats/StatsPanel.vue'
import LogFiltersSidebar from '@/components/LogTable/LogFiltersSidebar.vue'
import LogSearchBar from '@/components/LogTable/LogSearchBar.vue'
import LogTable from '@/components/LogTable/LogTable.vue'
import MessageDetailModal from '@/components/MessageDetail/MessageDetailModal.vue'
import { Bars3Icon, XMarkIcon } from '@heroicons/vue/24/outline'

const logStore = useLogStore()
const wsStore = useWebSocketStore()
const sidebarOpen = ref(false)

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