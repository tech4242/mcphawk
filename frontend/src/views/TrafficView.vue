<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api.js'
import { live } from '../live.js'
import { call, serverColor, STATUS_LABELS, when } from '../format.js'
import Waterfall from '../components/Waterfall.vue'
import ExchangeDetail from '../components/ExchangeDetail.vue'
import ProblemList from '../components/ProblemList.vue'
import CostReport from '../components/CostReport.vue'
import MessageLog from '../components/MessageLog.vue'

const props = defineProps({ runKey: String, sessionId: String })
const route = useRoute()
const router = useRouter()

const data = ref(null)
const error = ref(null)
const tab = ref(route.query.tab || 'timeline')
const text = ref('')
const status = ref('')
const bodyMatches = ref(null)

const selected = computed(() => (route.query.x ? Number(route.query.x) : null))

async function load() {
  try {
    if (props.runKey) {
      data.value = await api.run(props.runKey)
    } else {
      const session = await api.session(props.sessionId)
      data.value = {
        run_key: session.run_key, live: session.live, client_app: session.client_app,
        client_name: session.client_name, started_at: session.started_at,
        sessions: [session], timeline: session.exchanges,
      }
    }
    error.value = null
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)
let timer = null
watch(() => live.tick, () => {
  if (!data.value?.live) return
  clearTimeout(timer)
  timer = setTimeout(load, 300)
})

// Colour follows the server name, so a restarted server keeps its colour.
const servers = computed(() => {
  const byName = new Map()
  for (const s of data.value?.sessions || []) {
    const entry = byName.get(s.display_name)
    if (entry) entry.sessions.push(s)
    else byName.set(s.display_name, { name: s.display_name, latest: s, sessions: [s] })
    byName.get(s.display_name).latest = s
  }
  return [...byName.values()].map((server, i) => ({ ...server, color: serverColor(i) }))
})
const colors = computed(() => {
  const map = {}
  for (const server of servers.value) for (const s of server.sessions) map[s.id] = server.color
  return map
})
const names = computed(() => Object.fromEntries(
  (data.value?.sessions || []).map((s) => [s.id, s.display_name])))

let searchTimer = null
watch(text, (value) => {
  clearTimeout(searchTimer)
  if (value.trim().length < 3) { bodyMatches.value = null; return }
  searchTimer = setTimeout(async () => {
    const ids = new Set()
    for (const session of data.value?.sessions || []) {
      const hits = await api.exchanges({ session_id: session.id, q: value })
      hits.forEach((h) => ids.add(h.id))
    }
    bodyMatches.value = ids
  }, 250)
})

const rows = computed(() => {
  const needle = text.value.trim().toLowerCase()
  return (data.value?.timeline || []).filter((exchange) => {
    if (status.value === 'problems') {
      if (['ok', 'input_required', 'pending'].includes(exchange.status)) return false
    } else if (status.value && exchange.status !== status.value) return false
    if (!needle) return true
    const haystack = `${call(exchange)} ${names.value[exchange.session_id]}`.toLowerCase()
    return haystack.includes(needle) || bodyMatches.value?.has(exchange.id)
  })
})

const statusCounts = computed(() => {
  const counts = {}
  for (const e of data.value?.timeline || []) counts[e.status] = (counts[e.status] || 0) + 1
  return counts
})

const title = computed(() => {
  if (!data.value) return ''
  if (props.sessionId) return data.value.sessions[0].display_name
  if (props.runKey?.startsWith('replay:')) return 'Replay'
  return data.value.client_app || data.value.client_name || 'Run'
})

const scope = computed(() => (props.sessionId
  ? { session_id: props.sessionId } : { run_key: props.runKey }))

function select(id) {
  router.replace({ query: { ...route.query, x: id ?? undefined } })
}
function setTab(name) {
  tab.value = name
  router.replace({ query: { ...route.query, tab: name === 'timeline' ? undefined : name } })
}
</script>

<template>
  <div v-if="error" class="empty">
    <h2>Could not load this {{ sessionId ? 'session' : 'run' }}</h2>
    <p>{{ error }}. It may have been cleared.</p>
    <router-link to="/" class="btn">Back to latest run</router-link>
  </div>
  <div v-else-if="data" class="traffic" :class="{ drawer: selected }">
    <header class="head">
      <div class="title-row">
        <h1>{{ title }}</h1>
        <span v-if="data.live" class="live">live</span>
        <span class="faint">started {{ when(data.started_at) }}</span>
      </div>
      <div class="servers">
        <router-link v-for="server in servers" :key="server.name" :to="`/s/${server.latest.id}`"
                     class="server"
                     :title="`${server.latest.transport} via ${server.latest.capture}${server.latest.target ? ': ' + server.latest.target : ''}`">
          <span class="swatch" :style="{ background: server.color }" />
          <span>{{ server.name }}</span>
          <span v-if="server.latest.server_version" class="faint">{{ server.latest.server_version }}</span>
          <span v-if="server.latest.protocol_version" class="proto" :class="server.latest.era">
            {{ server.latest.protocol_version }}</span>
          <span v-if="server.sessions.length > 1" class="faint"
                title="The client started this server more than once">{{ server.sessions.length }} sessions</span>
        </router-link>
      </div>
      <div class="tabs" role="tablist">
        <button v-for="[name, label] in [['timeline', 'Timeline'], ['problems', 'Problems'],
                                         ['cost', 'Context cost'], ...(sessionId ? [['messages', 'Raw messages']] : [])]"
                :key="name" role="tab" :aria-selected="tab === name"
                :class="{ active: tab === name }" @click="setTab(name)">{{ label }}</button>
        <div v-if="tab === 'timeline'" class="filters">
          <input v-model="text" class="field" type="search" placeholder="Filter calls or search payloads"
                 aria-label="Filter calls" />
          <select v-model="status" class="field" aria-label="Status">
            <option value="">All statuses ({{ data.timeline.length }})</option>
            <option value="problems">Only problems</option>
            <option v-for="(count, key) in statusCounts" :key="key" :value="key">
              {{ STATUS_LABELS[key] || key }} ({{ count }})
            </option>
          </select>
        </div>
      </div>
    </header>

    <section class="body">
      <Waterfall v-if="tab === 'timeline'" :exchanges="rows" :colors="colors" :names="names"
                 :selected="selected" :multi="servers.length > 1" @select="select" />
      <ProblemList v-else-if="tab === 'problems'" :scope="scope" />
      <CostReport v-else-if="tab === 'cost'" :scope="scope" />
      <MessageLog v-else-if="tab === 'messages'" :session-id="sessionId" />
    </section>

    <ExchangeDetail v-if="selected" :id="selected" :key="selected" class="detail"
                    @close="select(null)" />
  </div>
</template>

<style scoped>
.traffic {
  display: grid; grid-template-columns: 1fr; grid-template-rows: auto 1fr;
  height: 100%; min-height: 0;
}
.traffic.drawer { grid-template-columns: minmax(0, 1fr) minmax(380px, 46%); }
.head { grid-column: 1; padding: 14px 18px 0; border-bottom: 1px solid var(--line); }
.title-row { display: flex; align-items: baseline; gap: 10px; }
h1 { font-size: 19px; font-weight: 600; margin: 0; }
.live {
  color: var(--ok); font-size: 12.5px; padding: 0 7px; border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--ok) 50%, transparent);
}
.servers { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 8px; }
.server {
  display: inline-flex; align-items: center; gap: 6px; text-decoration: none;
  padding: 2px 8px; border: 1px solid var(--line); border-radius: 12px; font-size: 13px;
}
.server:hover { border-color: var(--muted); }
.swatch { width: 9px; height: 9px; border-radius: 2px; }
.proto { font-family: var(--mono); font-size: 11.5px; color: var(--muted); }
.proto.modern { color: var(--ok); }
.tabs { display: flex; align-items: flex-end; gap: 2px; flex-wrap: wrap; }
.tabs button {
  background: none; border: 0; border-bottom: 2px solid transparent;
  padding: 7px 10px; color: var(--muted); cursor: pointer;
}
.tabs button.active { color: var(--text); border-bottom-color: var(--brand); }
.filters { margin-left: auto; display: flex; gap: 6px; padding-bottom: 6px; }
.filters input { width: 240px; }
.body { grid-column: 1; min-height: 0; overflow: auto; }
.detail { grid-column: 2; grid-row: 1 / span 2; }
@media (max-width: 1000px) {
  .traffic.drawer { grid-template-columns: 1fr; }
  .detail { position: fixed; inset: 0 0 0 auto; width: min(100%, 560px); z-index: 5; }
}
</style>
