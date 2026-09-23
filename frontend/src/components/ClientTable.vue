<script setup>
defineProps({ servers: { type: Array, required: true } })

const CLIENTS = {
  'claude-desktop': 'Claude Desktop', 'claude-code': 'Claude Code',
  cursor: 'Cursor', vscode: 'VS Code',
}
const captured = (s) => ['already wrapped', 'already proxied'].includes(s.status)
const scope = (s) => (s.scope === 'user' ? '' : s.scope.startsWith('local:')
  ? `project ${s.scope.slice(6).split('/').pop()}` : s.scope)
function statusText(s) {
  if (captured(s)) return 'Recorded'
  if (s.status.startsWith('would')) return 'Not yet: run mcphawk install'
  if (s.status.startsWith('HTTP server')) return 'Not yet: mcphawk install --include-http'
  if (s.status.includes('OAuth')) return 'Skipped: uses OAuth (--force-http to try)'
  if (s.status === 'this is MCPHawk itself') return 'MCPHawk itself'
  return s.status.charAt(0).toUpperCase() + s.status.slice(1)
}
</script>

<template>
  <table class="grid">
    <thead><tr><th>Client</th><th>Server</th><th>Status</th></tr></thead>
    <tbody>
      <tr v-for="s in servers" :key="s.file + s.scope + s.server">
        <td :title="s.file">{{ CLIENTS[s.client] || s.client }}<span v-if="scope(s)" class="faint">
          ({{ scope(s) }})</span></td>
        <td class="mono">{{ s.server }}</td>
        <td :class="{ ok: captured(s), todo: s.status.startsWith('would') }">{{ statusText(s) }}</td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.ok { color: var(--ok); }
.todo { color: var(--hung); }
</style>
