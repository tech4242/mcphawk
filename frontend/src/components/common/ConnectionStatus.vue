<template>
  <div class="flex items-center">
    <div 
      class="w-2 h-2 rounded-full mr-2"
      :class="statusClass"
    ></div>
    <span class="text-sm text-gray-600 dark:text-gray-400">
      {{ statusText }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'

const wsStore = useWebSocketStore()

const statusClass = computed(() => {
  if (wsStore.connected) {
    return 'bg-green-500 animate-pulse-slow'
  }
  if (wsStore.reconnectAttempts > 0) {
    return 'bg-yellow-500 animate-pulse'
  }
  return 'bg-red-500'
})

const statusText = computed(() => {
  if (wsStore.connected) {
    return 'Connected'
  }
  if (wsStore.reconnectAttempts > 0) {
    return `Reconnecting (${wsStore.reconnectAttempts})...`
  }
  return 'Disconnected'
})
</script>