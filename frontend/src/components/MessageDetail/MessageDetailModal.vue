<template>
  <TransitionRoot :show="!!logStore.selectedLog" as="template">
    <Dialog as="div" class="relative z-50" @close="logStore.selectLog(null)">
      <TransitionChild
        as="template"
        enter="duration-300 ease-out"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="duration-200 ease-in"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="fixed inset-0 bg-black bg-opacity-25" />
      </TransitionChild>

      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4 text-center">
          <TransitionChild
            as="template"
            enter="duration-300 ease-out"
            enter-from="opacity-0 scale-95"
            enter-to="opacity-100 scale-100"
            leave="duration-200 ease-in"
            leave-from="opacity-100 scale-100"
            leave-to="opacity-0 scale-95"
          >
            <DialogPanel class="w-full max-w-4xl transform overflow-hidden rounded-2xl bg-white dark:bg-gray-800 p-6 text-left align-middle shadow-xl transition-all">
              <DialogTitle as="h3" class="text-lg font-medium leading-6 text-gray-900 dark:text-gray-100 mb-4">
                Message Details
              </DialogTitle>
              
              <div v-if="logStore.selectedLog" class="space-y-4">
                <!-- Message metadata -->
                <div class="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span class="text-gray-500 dark:text-gray-400">Time:</span>
                    <span class="ml-2 font-mono text-gray-900 dark:text-gray-100">
                      {{ new Date(logStore.selectedLog.timestamp).toLocaleString() }}
                    </span>
                  </div>
                  <div>
                    <span class="text-gray-500 dark:text-gray-400">Type:</span>
                    <MessageTypeBadge :type="messageType" class="ml-2" />
                  </div>
                  <div>
                    <span class="text-gray-500 dark:text-gray-400">Source:</span>
                    <span class="ml-2 font-mono text-gray-900 dark:text-gray-100">
                      {{ logStore.selectedLog.src_ip }}:{{ logStore.selectedLog.src_port }}
                    </span>
                  </div>
                  <div>
                    <span class="text-gray-500 dark:text-gray-400">Destination:</span>
                    <span class="ml-2 font-mono text-gray-900 dark:text-gray-100">
                      {{ logStore.selectedLog.dst_ip }}:{{ logStore.selectedLog.dst_port }}
                    </span>
                  </div>
                </div>

                <!-- JSON content -->
                <div class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                  <div class="bg-gray-50 dark:bg-gray-700 px-4 py-2 flex justify-between items-center">
                    <span class="text-sm font-medium text-gray-700 dark:text-gray-300">JSON-RPC Message</span>
                    <button
                      @click="copyToClipboard"
                      class="text-sm text-mcp-blue hover:text-blue-600 flex items-center gap-1"
                    >
                      <ClipboardDocumentIcon class="h-4 w-4" />
                      {{ copied ? 'Copied!' : 'Copy' }}
                    </button>
                  </div>
                  <div class="p-4 bg-gray-900 overflow-x-auto">
                    <pre class="text-sm text-gray-100 font-mono whitespace-pre">{{ formattedJson }}</pre>
                  </div>
                </div>

                <!-- Paired Messages -->
                <PairedMessages 
                  v-if="logStore.selectedLog"
                  :current-log="logStore.selectedLog" 
                  :all-logs="logStore.logs" 
                  variant="full" 
                  class="mt-4"
                />

                <!-- Actions -->
                <div class="flex justify-end gap-2 mt-6">
                  <button
                    @click="exportLog"
                    class="btn-secondary"
                  >
                    Export
                  </button>
                  <button
                    @click="logStore.selectLog(null)"
                    class="btn-primary"
                  >
                    Close
                  </button>
                </div>
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'
import { ClipboardDocumentIcon } from '@heroicons/vue/24/outline'
import { useLogStore } from '@/stores/logs'
import { getMessageType, parseMessage } from '@/utils/messageParser'
import MessageTypeBadge from '@/components/LogTable/MessageTypeBadge.vue'
import PairedMessages from '@/components/common/PairedMessages.vue'

const logStore = useLogStore()
const copied = ref(false)

const messageType = computed(() => {
  if (!logStore.selectedLog) return 'unknown'
  return getMessageType(logStore.selectedLog.message)
})

const formattedJson = computed(() => {
  if (!logStore.selectedLog) return ''
  const parsed = parseMessage(logStore.selectedLog.message)
  return JSON.stringify(parsed, null, 2)
})

async function copyToClipboard() {
  try {
    await navigator.clipboard.writeText(formattedJson.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}

function exportLog() {
  const log = logStore.selectedLog
  const filename = `mcp-log-${log.timestamp.replace(/[:.]/g, '-')}.json`
  const data = {
    ...log,
    parsed_message: parseMessage(log.message)
  }
  
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>