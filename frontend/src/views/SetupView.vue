<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'
import ClientTable from '../components/ClientTable.vue'

defineProps({ firstRun: Boolean })
const servers = ref(null)
const error = ref(null)
const origin = window.location.origin

onMounted(async () => {
  try {
    servers.value = (await api.setup()).servers
  } catch (e) {
    error.value = e.message
  }
})

const captured = (s) => ['already wrapped', 'already proxied'].includes(s.status)
const routed = computed(() => (servers.value || []).filter(captured).length)
</script>

<template>
  <div class="page">
    <h1>{{ firstRun ? 'Capture your first MCP traffic' : 'Setup' }}</h1>
    <p v-if="firstRun" class="lead">Nothing has been recorded yet. MCPHawk sees traffic once your
      client's servers run through it; nothing else about them changes.</p>

    <section v-if="servers && routed" class="clients">
      <h2>Your clients</h2>
      <p class="muted">{{ routed }} of {{ servers.length }} MCP servers are recorded.</p>
      <ClientTable :servers="servers" />
    </section>

    <h2>{{ routed ? 'Record more servers' : '1. Route your servers through MCPHawk' }}</h2>
    <p>Finds the MCP servers of Claude Desktop, Claude Code, Cursor and VS Code, backs up each
      config file and records every server that can be recorded safely. Restart the clients
      afterwards.</p>
    <pre>mcphawk install</pre>
    <p class="faint">Add <code>--include-http</code> for local HTTP servers. Undo everything with
      <code>mcphawk uninstall</code>. For a single server, prefix its command with
      <code>mcphawk wrap --</code>.</p>

    <h2>{{ routed ? 'Let your agent read the traffic' : '2. Let your agent read the traffic too' }}</h2>
    <p>Give Claude Code (or any MCP client) the MCPHawk tools, so it can find failing calls and
      context hogs itself and link you straight to them.</p>
    <pre>claude mcp add mcphawk -- mcphawk mcp</pre>
    <p class="faint">Or connect over HTTP while this page is running: <code>{{ origin }}/mcp</code></p>

    <p v-if="error" class="err">{{ error }}</p>
    <p v-else-if="servers && !servers.length" class="faint">No MCP client configuration was found
      in the usual places.</p>
    <section v-else-if="servers && !routed" class="clients">
      <h2>Your clients</h2>
      <ClientTable :servers="servers" />
    </section>
  </div>
</template>

<style scoped>
.page { overflow: auto; height: 100%; padding: 20px 24px 40px; }
.page > * { max-width: 72ch; }
.clients { max-width: 900px; }
.clients h2:first-child { margin-top: 12px; }
h1 { font-size: 22px; font-weight: 600; margin: 0 0 8px; }
h2 { font-size: 15px; font-weight: 600; margin: 26px 0 6px; }
.lead { font-size: 15px; color: var(--muted); }
pre {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 10px 12px; font-size: 13.5px; user-select: all;
}
.ok { color: var(--ok); }
.todo { color: var(--hung); }
.err { color: var(--error); }
</style>
