<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import SetupView from './SetupView.vue'

const router = useRouter()
const empty = ref(false)

onMounted(async () => {
  const runs = await api.runs()
  if (runs.length) {
    const latest = runs.find((r) => !r.run_key.startsWith('replay:')) || runs[0]
    router.replace(`/r/${encodeURIComponent(latest.run_key)}`)
  } else {
    empty.value = true
  }
})
</script>

<template>
  <SetupView v-if="empty" first-run />
</template>
