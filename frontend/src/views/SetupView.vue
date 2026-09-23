<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

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

const routed = computed(() => (servers.value || []).filter((s) =>
  ['already wrapped', 'already proxied'].includes(s.status)).length)
</script>

<template>
  <div class="page">
    <h1>{{ firstRun ? 'Capture your first MCP traffic' : 'Setup' }}</h1>
    <p v-if="firstRun" class="lead">Nothing has been recorded yet. MCPHawk sees traffic once your
      client's servers run through it; nothing else about them changes.</p>

    <h2>1. Route your servers through MCPHawk</h2>
    <p>Wraps every stdio server of Claude Desktop, Claude Code, Cursor and VS Code, with a
      backup of each config file. Restart the clients afterwards.</p>
    <pre>mcphawk install</pre>
    <p class="faint">Add <code>--include-http</code> for local HTTP servers. Undo everything with
      <code>mcphawk uninstall</code>. For a single server, prefix its command with
      <code>mcphawk wrap --</code>.</p>

    <h2>2. Let your agent read the traffic too</h2>
    <p>Give Claude Code (or any MCP client) the MCPHawk tools, so it can find failing calls and
      context hogs itself and link you straight to them.</p>
    <pre>claude mcp add mcphawk -- mcphawk mcp</pre>
    <p class="faint">Or connect over HTTP while this page is running: <code>{{ origin }}/mcp</code></p>

    <h2>Your clients</h2>
    <p v-if="error" class="err">{{ error }}</p>
    <p v-else-if="servers && !servers.length" class="faint">No MCP client configuration was found
      in the usual places.</p>
    <template v-else-if="servers">
      <p class="muted">{{ routed }} of {{ servers.length }} servers go through MCPHawk.</p>
      <table class="grid">
        <thead><tr><th>Client</th><th>Server</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="s in servers" :key="s.file + s.scope + s.server">
            <td :title="s.file">{{ s.client }}<span v-if="s.scope !== 'user'" class="faint"> ({{ s.scope }})</span></td>
            <td class="mono">{{ s.server }}</td>
            <td :class="{ ok: s.status.startsWith('already'), todo: s.status.startsWith('would') }">
              {{ s.status.startsWith('already') ? 'captured' : s.status }}
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<style scoped>
.page { overflow: auto; height: 100%; padding: 20px 24px 40px; }
.page > * { max-width: 72ch; }
.page > table { max-width: 900px; }
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
