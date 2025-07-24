<template>
  <tr>
    <td colspan="5" class="p-0">
      <div 
        class="cursor-pointer transition-colors"
        :class="{
          'bg-blue-50 dark:bg-blue-900/20': isSelected,
          'ring-2 ring-blue-400 ring-opacity-50': isPaired && !isSelected,
          'hover:bg-gray-50 dark:hover:bg-gray-700/50': !isSelected
        }"
        @click="$emit('click')"
      >
        <table class="w-full table-fixed">
          <tr>
            <td class="px-4 py-3 text-left w-32 text-sm text-gray-900 dark:text-gray-100">
              {{ formatTimestamp(log.timestamp) }}
            </td>
            <td class="px-4 py-3 text-left w-28">
              <MessageTypeBadge :type="messageType" />
            </td>
            <td class="px-4 py-3 text-left text-sm text-gray-900 dark:text-gray-100 font-mono truncate">
              {{ messageSummary }}
            </td>
            <td class="px-4 py-3 text-left w-48 text-sm text-gray-500 dark:text-gray-400">
              <div class="flex items-center">
                <span>{{ log.src_ip }}</span>
                <span class="mx-2">{{ directionIcon }}</span>
                <span>{{ log.dst_ip }}</span>
              </div>
            </td>
            <td class="px-4 py-3 text-left w-24 text-sm text-gray-500 dark:text-gray-400 font-mono">
              {{ portInfo }}
            </td>
          </tr>
        </table>
      </div>
      <!-- Expanded JSON view -->
      <div v-if="isExpanded" class="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700">
        <pre class="text-xs font-mono text-gray-800 dark:text-gray-200 overflow-x-auto">{{ formattedJson }}</pre>
      </div>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue'
import { getMessageType, getMessageSummary, formatTimestamp, getPortInfo, getDirectionIcon } from '@/utils/messageParser'
import MessageTypeBadge from './MessageTypeBadge.vue'

const props = defineProps({
  log: {
    type: Object,
    required: true
  },
  isSelected: {
    type: Boolean,
    default: false
  },
  isPaired: {
    type: Boolean,
    default: false
  },
  isExpanded: {
    type: Boolean,
    default: false
  }
})

defineEmits(['click'])

const messageType = computed(() => getMessageType(props.log.message))
const messageSummary = computed(() => getMessageSummary(props.log.message))
const portInfo = computed(() => getPortInfo(props.log))
const directionIcon = computed(() => getDirectionIcon(props.log.direction))

const formattedJson = computed(() => {
  try {
    const parsed = JSON.parse(props.log.message)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return props.log.message
  }
})
</script>