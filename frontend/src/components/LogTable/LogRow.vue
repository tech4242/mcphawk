<template>
  <tr>
    <td colspan="10" class="p-0">
      <div 
        class="cursor-pointer transition-all relative"
        :class="{
          'bg-blue-100 dark:bg-blue-900/30 ring-2 ring-blue-500': isSelected,
          'hover:bg-gray-50 dark:hover:bg-gray-700/50': !isSelected
        }"
        @click="$emit('click')"
      >
        <table class="w-full table-fixed">
          <tr>
            <td class="px-4 py-3 text-left w-24 text-sm text-gray-900 dark:text-gray-100">
              {{ formatDate(log.timestamp) }}
            </td>
            <td class="px-4 py-3 text-left w-32 text-sm text-gray-900 dark:text-gray-100">
              {{ formatTimestamp(log.timestamp) }}
            </td>
            <td class="px-4 py-3 text-left w-32">
              <MessageTypeBadge :type="messageType" />
            </td>
            <td class="px-4 py-3 text-left w-20 text-sm text-gray-900 dark:text-gray-100 font-mono">
              <span class="text-gray-600 dark:text-gray-400">{{ messageId }}</span>
            </td>
            <td class="px-4 py-3 text-left text-sm text-gray-900 dark:text-gray-100 font-mono truncate">
              {{ messageSummary }}
            </td>
            <td class="px-4 py-3 text-left w-40 text-sm text-gray-500 dark:text-gray-400">
              <span v-if="serverInfo" 
                    class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200"
                    :title="`${serverInfo.name} v${serverInfo.version}`">
                {{ serverInfo.name }}
              </span>
              <span v-else class="text-gray-400 dark:text-gray-600">-</span>
            </td>
            <td class="px-4 py-3 text-left w-32 text-sm text-gray-500 dark:text-gray-400 font-mono">
              <span 
                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                :class="transportTypeColor"
              >
                {{ formattedTransportType }}
              </span>
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
            <td class="px-4 py-3 text-left w-20 text-sm text-gray-500 dark:text-gray-400 font-mono">
              {{ pidInfo }}
            </td>
          </tr>
        </table>
      </div>
      <!-- Expanded JSON view -->
      <div v-if="isExpanded" class="bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700">
        <!-- Message metadata -->
        <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span class="text-gray-500 dark:text-gray-400">Date:</span>
              <span class="ml-2 font-mono text-gray-900 dark:text-gray-100">
                {{ formatDate(log.timestamp) }}
              </span>
            </div>
            <div>
              <span class="text-gray-500 dark:text-gray-400">Time:</span>
              <span class="ml-2 font-mono text-gray-900 dark:text-gray-100">
                {{ formatTimestamp(log.timestamp) }}
              </span>
            </div>
            <div>
              <span class="text-gray-500 dark:text-gray-400">Type:</span>
              <MessageTypeBadge :type="messageType" class="ml-2" />
            </div>
            <div>
              <span class="text-gray-500 dark:text-gray-400">Message ID:</span>
              <span class="ml-2 font-mono text-gray-900 dark:text-gray-100">
                {{ messageId }}
              </span>
            </div>
            <div>
              <span class="text-gray-500 dark:text-gray-400">Server:</span>
              <span v-if="serverInfo" class="ml-2 text-gray-900 dark:text-gray-100">
                {{ serverInfo.name }} <span class="text-gray-500 dark:text-gray-400">v{{ serverInfo.version }}</span>
              </span>
              <span v-else class="ml-2 text-gray-500 dark:text-gray-400">-</span>
            </div>
            <div v-if="clientInfo">
              <span class="text-gray-500 dark:text-gray-400">Client:</span>
              <span class="ml-2 text-gray-900 dark:text-gray-100">
                {{ clientInfo.name }} <span class="text-gray-500 dark:text-gray-400">v{{ clientInfo.version }}</span>
              </span>
            </div>
            <div>
              <span class="text-gray-500 dark:text-gray-400">Transport:</span>
              <span 
                class="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                :class="transportTypeColor"
              >
                {{ formattedTransportType }}
              </span>
            </div>
            <div>
              <span class="text-gray-500 dark:text-gray-400">Direction:</span>
              <span class="ml-2 text-gray-900 dark:text-gray-100">
                {{ log.src_ip }} {{ directionIcon }} {{ log.dst_ip }}
              </span>
            </div>
            <div v-if="log.src_port || log.dst_port">
              <span class="text-gray-500 dark:text-gray-400">Ports:</span>
              <span class="ml-2 font-mono text-gray-900 dark:text-gray-100">
                {{ portInfo }}
              </span>
            </div>
            <div v-if="log.pid">
              <span class="text-gray-500 dark:text-gray-400">PID:</span>
              <span class="ml-2 font-mono text-gray-900 dark:text-gray-100">
                {{ log.pid }}
              </span>
            </div>
            <div v-if="log.log_id">
              <span class="text-gray-500 dark:text-gray-400">Log ID:</span>
              <span class="ml-2 font-mono text-gray-900 dark:text-gray-100 text-xs">
                {{ log.log_id }}
              </span>
            </div>
          </div>
        </div>
        
        <!-- JSON content -->
        <div class="px-4 py-3">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">JSON-RPC Message:</div>
          <pre class="text-xs font-mono text-gray-800 dark:text-gray-200 overflow-x-auto bg-gray-100 dark:bg-gray-800 p-3 rounded">{{ formattedJson }}</pre>
        </div>
        
        <!-- Paired messages -->
        <PairedMessages 
          :current-log="log" 
          :all-logs="allLogs" 
          variant="compact" 
        />
      </div>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue'
import { getMessageType, getMessageSummary, formatTimestamp, formatDate, getPortInfo, getDirectionIcon } from '@/utils/messageParser'
import { formatTransportType, getTransportTypeColor } from '@/utils/transportFormatter'
import MessageTypeBadge from './MessageTypeBadge.vue'
import PairedMessages from '@/components/common/PairedMessages.vue'

const props = defineProps({
  log: {
    type: Object,
    required: true
  },
  allLogs: {
    type: Array,
    default: () => []
  },
  isSelected: {
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

const messageId = computed(() => {
  try {
    const parsed = JSON.parse(props.log.message)
    if (parsed && parsed.id !== undefined) {
      return parsed.id
    }
  } catch {
    // ignore
  }
  return '-'
})
const directionIcon = computed(() => getDirectionIcon(props.log.direction))

const formattedJson = computed(() => {
  try {
    const parsed = JSON.parse(props.log.message)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return props.log.message
  }
})

const formattedTransportType = computed(() => {
  return formatTransportType(props.log.transport_type || props.log.traffic_type || 'unknown')
})

const transportTypeColor = computed(() => {
  return getTransportTypeColor(props.log.transport_type || props.log.traffic_type || 'unknown')
})

const pidInfo = computed(() => {
  // For stdio transport, show PID; for network transports, show empty
  if (props.log.transport_type === 'stdio' && props.log.pid) {
    return props.log.pid.toString()
  }
  return '-'
})

const serverInfo = computed(() => {
  if (!props.log.metadata) return null
  try {
    const meta = JSON.parse(props.log.metadata)
    if (meta.server_name) {
      return {
        name: meta.server_name,
        version: meta.server_version || ''
      }
    }
  } catch {
    // ignore
  }
  return null
})

const clientInfo = computed(() => {
  if (!props.log.metadata) return null
  try {
    const meta = JSON.parse(props.log.metadata)
    if (meta.client_name) {
      return {
        name: meta.client_name,
        version: meta.client_version || ''
      }
    }
  } catch {
    // ignore
  }
  return null
})

</script>