<template>
  <span 
    class="message-badge"
    :class="badgeClass"
  >
    {{ displayText }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: {
    type: String,
    required: true
  }
})

const badgeClass = computed(() => {
  switch (props.type) {
    case 'request':
      return 'message-request'
    case 'response':
      return 'message-response'
    case 'notification':
      return 'message-notification'
    case 'error':
      return 'message-error'
    default:
      return 'bg-gray-100 text-gray-800'
  }
})

const displayText = computed(() => {
  switch (props.type) {
    case 'request':
      return 'REQ'
    case 'response':
      return 'RES'
    case 'notification':
      return 'NOTIF'
    case 'error':
      return 'ERR'
    default:
      return 'UNK'
  }
})
</script>