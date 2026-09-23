<script setup>
import { ref, watch, onMounted } from 'vue'
import { api } from '../api.js'
import { live } from '../live.js'
import { timeRange } from '../format.js'

const runs = ref([])
const error = ref(null)

async function load() {
  try {
    runs.value = await api.runs()
    error.value = null
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)
let timer = null
watch(() => live.tick, () => {
  clearTimeout(timer)
  timer = setTimeout(load, 400)
})
</script>

<template>
  <div class="runs">
    <h2>Agent runs</h2>
    <p class="hint faint pad">Everything one client did in one stretch of work, across all
      its MCP servers. A pause of 5 minutes starts a new run.</p>
    <p v-if="error" class="faint pad">{{ error }}</p>
    <p v-else-if="!runs.length" class="faint pad">No traffic yet.</p>
    <router-link v-for="run in runs" :key="run.run_key"
                 :to="`/r/${encodeURIComponent(run.run_key)}`" class="run">
      <span class="top">
        <span class="live" v-if="run.live" title="Still running" />
        <strong>{{ run.client }}</strong>
        <span class="faint when">{{ timeRange(run.started_at, run.last_seen_at) }}</span>
      </span>
      <span class="servers muted">{{ run.servers.join(', ') }}</span>
      <span class="counts faint">
        {{ run.servers.length }} server{{ run.servers.length === 1 ? '' : 's' }},
        {{ run.exchange_count }} call{{ run.exchange_count === 1 ? '' : 's' }}<template
          v-if="run.error_count">, <span class="err">{{ run.error_count }} failed</span></template>
      </span>
    </router-link>
  </div>
</template>

<style scoped>
.runs { overflow-y: auto; padding: 8px; flex: 1; }
h2 { font-size: 12.5px; font-weight: 500; color: var(--muted); margin: 4px 8px 6px; }
.pad { padding: 0 8px; }
.hint { font-size: 12px; margin: 0 0 8px; line-height: 1.4; }
.run {
  display: flex; flex-direction: column; gap: 1px;
  padding: 7px 8px; border-radius: var(--radius); text-decoration: none;
  border: 1px solid transparent;
}
.run:hover { background: var(--raised); }
.run.router-link-active { background: var(--raised); border-color: var(--line); }
.top { display: flex; align-items: center; gap: 6px; }
.when { margin-left: auto; font-size: 12px; }
.live { width: 6px; height: 6px; border-radius: 50%; background: var(--ok); flex: none; }
.servers { font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.counts { font-size: 12px; }
.err { color: var(--error); }
</style>
