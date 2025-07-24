<template>
  <tr 
    class="cursor-pointer transition-colors"
    :class="{
      'bg-blue-50 dark:bg-blue-900/20': isSelected,
      'ring-2 ring-blue-400 ring-opacity-50': isPaired && !isSelected,
      'hover:bg-gray-50 dark:hover:bg-gray-700/50': !isSelected
    }"
    @click="$emit('click')"
  >
    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
      {{ formatTimestamp(log.timestamp) }}
    </td>
    <td class="px-4 py-3 whitespace-nowrap">
      <MessageTypeBadge :type="messageType" />
    </td>
    <td class="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 font-mono truncate max-w-md">
      {{ messageSummary }}
    </td>
    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
      <div class="flex items-center">
        <span>{{ log.src_ip }}</span>
        <span class="mx-2">{{ directionIcon }}</span>
        <span>{{ log.dst_ip }}</span>
      </div>
    </td>
    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400 font-mono">
      {{ portInfo }}
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
  }
})

defineEmits(['click'])

const messageType = computed(() => getMessageType(props.log.message))
const messageSummary = computed(() => getMessageSummary(props.log.message))
const portInfo = computed(() => getPortInfo(props.log))
const directionIcon = computed(() => getDirectionIcon(props.log.direction))
</script>