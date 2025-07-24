<template>
  <div v-if="pairedMessages.length > 0" :class="containerClass">
    <div :class="headerClass">
      <span class="text-sm font-medium text-gray-700 dark:text-gray-300">
        Paired {{ pairedMessages.length === 1 ? 'Message' : 'Messages' }} (same JSON-RPC ID)
      </span>
    </div>
    <div :class="contentClass">
      <div v-for="(pairedLog, index) in pairedMessages" :key="index" :class="messageClass">
        <div :class="messageHeaderClass">
          <div class="flex items-center gap-3">
            <MessageTypeBadge :type="getMessageType(pairedLog.message)" />
            <span class="text-gray-600 dark:text-gray-400">{{ formatTimestamp(pairedLog.timestamp) }}</span>
          </div>
          <span class="text-xs text-gray-500 dark:text-gray-500 font-mono">
            {{ pairedLog.src_ip }}:{{ pairedLog.src_port }} → {{ pairedLog.dst_ip }}:{{ pairedLog.dst_port }}
          </span>
        </div>
        <div :class="messageContentClass">
          <pre class="text-xs font-mono text-gray-800 dark:text-gray-200 whitespace-pre overflow-x-auto">{{ formatPairedJson(pairedLog.message) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getMessageType, formatTimestamp } from '@/utils/messageParser'
import MessageTypeBadge from '@/components/LogTable/MessageTypeBadge.vue'

const props = defineProps({
  currentLog: {
    type: Object,
    required: true
  },
  allLogs: {
    type: Array,
    required: true
  },
  variant: {
    type: String,
    default: 'compact' // 'compact' for LogRow, 'full' for Modal
  }
})

const pairedMessages = computed(() => {
  if (!props.allLogs.length) return []
  
  try {
    const parsed = JSON.parse(props.currentLog.message)
    if (!parsed.id) return []
    
    // Find all messages with the same JSON-RPC ID, excluding the current one
    return props.allLogs.filter(log => {
      if (log === props.currentLog) return false
      try {
        const otherParsed = JSON.parse(log.message)
        return otherParsed.id === parsed.id
      } catch {
        return false
      }
    })
  } catch {
    return []
  }
})

function formatPairedJson(message) {
  try {
    const parsed = JSON.parse(message)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return message
  }
}

// Computed classes based on variant
const containerClass = computed(() => {
  return props.variant === 'full' 
    ? 'border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden'
    : 'border-t border-gray-200 dark:border-gray-700 px-4 py-3'
})

const headerClass = computed(() => {
  return props.variant === 'full'
    ? 'bg-gray-50 dark:bg-gray-700 px-4 py-2'
    : 'text-xs font-medium text-gray-600 dark:text-gray-400 mb-2'
})

const contentClass = computed(() => {
  return props.variant === 'full'
    ? 'p-4 space-y-4 max-h-96 overflow-y-auto'
    : ''
})

const messageClass = computed(() => {
  return props.variant === 'full'
    ? 'border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden'
    : 'mb-3 last:mb-0'
})

const messageHeaderClass = computed(() => {
  return props.variant === 'full'
    ? 'bg-gray-100 dark:bg-gray-800 px-3 py-2 flex items-center justify-between text-sm'
    : 'flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 mb-1'
})

const messageContentClass = computed(() => {
  return props.variant === 'full'
    ? 'p-3 bg-gray-50 dark:bg-gray-900'
    : 'bg-gray-100 dark:bg-gray-800 rounded p-2'
})
</script>