<template>
  <div class="flex-1 flex overflow-hidden">
    <!-- Sidebar -->
    <aside
      :class="[
        'w-64 flex-shrink-0 overflow-hidden transition-all duration-300',
        windowWidth < 1024 
          ? 'fixed inset-y-0 left-0 z-40' 
          : 'relative',
        sidebarOpen 
          ? 'translate-x-0' 
          : '-translate-x-full lg:hidden'
      ]"
    >
      <div class="h-full lg:h-full" :class="{'mt-16': true, 'lg:mt-0': true}">
        <LogFiltersSidebar />
      </div>
    </aside>

    <!-- Mobile sidebar backdrop -->
    <div
      v-if="sidebarOpen && windowWidth < 1024"
      @click="sidebarOpen = false"
      class="fixed inset-0 bg-black/50 z-30 mt-16"
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
</template>

<script setup>
import { inject, onMounted, onUnmounted, ref } from 'vue'
import LogFiltersSidebar from '@/components/LogTable/LogFiltersSidebar.vue'
import LogSearchBar from '@/components/LogTable/LogSearchBar.vue'
import LogTable from '@/components/LogTable/LogTable.vue'

const sidebarOpen = inject('sidebarOpen')
const windowWidth = ref(window.innerWidth)

// Handle window resize
const handleResize = () => {
  windowWidth.value = window.innerWidth
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  handleResize() // Initial check
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>