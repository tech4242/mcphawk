<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()
const error = ref(null)

onMounted(async () => {
  try {
    const exchange = await api.exchange(props.id)
    router.replace(`/s/${exchange.session_id}?x=${exchange.id}`)
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div v-if="error" class="empty">
    <h2>This call is no longer recorded</h2>
    <p>{{ error }}. Captured traffic may have been cleared since the link was shared.</p>
  </div>
</template>
