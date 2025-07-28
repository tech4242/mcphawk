<template>
  <div class="flex items-center space-x-4">
    <!-- WebSocket Status -->
    <div class="flex items-center">
      <div 
        class="w-2 h-2 rounded-full mr-2"
        :class="wsStatusClass"
      ></div>
      <span class="text-sm text-gray-600 dark:text-gray-400">
        {{ wsStatusText }}
      </span>
    </div>
    
    <!-- MCP Server Status -->
    <div class="flex items-center">
      <div 
        class="w-2 h-2 rounded-full mr-2"
        :class="mcpStatusClass"
      ></div>
      <span class="text-sm text-gray-600 dark:text-gray-400">
        MCP Server
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'

const wsStore = useWebSocketStore()
const withMcp = ref(false)

// Check MCP status on mount
onMounted(async () => {
  try {
    const response = await fetch('/status')
    const data = await response.json()
    withMcp.value = data.with_mcp
  } catch (error) {
    console.error('Failed to fetch server status:', error)
  }
})

const wsStatusClass = computed(() => {
  if (wsStore.connected) {
    return 'bg-green-500 animate-pulse-slow'
  }
  if (wsStore.reconnectAttempts > 0) {
    return 'bg-yellow-500 animate-pulse'
  }
  return 'bg-red-500'
})

const wsStatusText = computed(() => {
  if (wsStore.connected) {
    return 'Live Updates'
  }
  if (wsStore.reconnectAttempts > 0) {
    return `Reconnecting (${wsStore.reconnectAttempts})...`
  }
  return 'Disconnected'
})

const mcpStatusClass = computed(() => {
  if (withMcp.value) {
    return 'bg-green-500 animate-pulse-slow'
  }
  return 'bg-gray-400'
})
</script>