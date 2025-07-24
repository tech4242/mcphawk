<template>
  <div class="flex items-center space-x-4 text-sm">
    <div class="flex items-center space-x-2">
      <span class="text-gray-500 dark:text-gray-400">Total:</span>
      <span class="font-medium text-gray-900 dark:text-gray-100">{{ stats.total }}</span>
    </div>
    <div class="flex items-center space-x-2">
      <div class="w-2 h-2 rounded-full bg-blue-500"></div>
      <span class="text-gray-500 dark:text-gray-400">Req:</span>
      <span class="font-medium text-gray-900 dark:text-gray-100">{{ stats.requests }}</span>
    </div>
    <div class="flex items-center space-x-2">
      <div class="w-2 h-2 rounded-full bg-green-500"></div>
      <span class="text-gray-500 dark:text-gray-400">Res:</span>
      <span class="font-medium text-gray-900 dark:text-gray-100">{{ stats.responses }}</span>
    </div>
    <div class="flex items-center space-x-2">
      <div class="w-2 h-2 rounded-full bg-yellow-500"></div>
      <span class="text-gray-500 dark:text-gray-400">Notif:</span>
      <span class="font-medium text-gray-900 dark:text-gray-100">{{ stats.notifications }}</span>
    </div>
    <div class="flex items-center space-x-2" v-if="stats.errors > 0">
      <div class="w-2 h-2 rounded-full bg-red-500"></div>
      <span class="text-gray-500 dark:text-gray-400">Err:</span>
      <span class="font-medium text-red-600 dark:text-red-400">{{ stats.errors }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useLogStore } from '@/stores/logs'

const logStore = useLogStore()
const stats = computed(() => logStore.stats)
</script>