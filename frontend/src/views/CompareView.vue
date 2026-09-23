<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api.js'
import { ms, tokens, when } from '../format.js'

const route = useRoute()
const router = useRouter()
const sessions = ref([])
const before = ref(route.query.before || '')
const after = ref(route.query.after || '')
const report = ref(null)
const error = ref(null)

onMounted(async () => {
  sessions.value = await api.sessions({ limit: 200 })
  if (!before.value && !after.value) {
    // Default: the newest real session, against the previous one of the same server.
    const server = (s) => s.server_name || s.display_name
    const real = sessions.value.filter((s) => s.capture !== 'replay')
    const pair = real.find((s, i) => real.slice(i + 1).some((o) => server(o) === server(s)))
    if (pair) {
      after.value = pair.id
      before.value = real.find((o) => o !== pair && o.started_at < pair.started_at
        && server(o) === server(pair)).id
    }
  }
})

watch([before, after], async ([b, a]) => {
  report.value = null
  error.value = null
  if (!b || !a) return
  router.replace({ query: { before: b, after: a } })
  try {
    report.value = await api.compare(b, a)
  } catch (e) {
    error.value = e.message
  }
}, { immediate: true })

function label(s) {
  return `${s.display_name}, ${when(s.started_at)}${s.server_version ? `, v${s.server_version}` : ''}`
}
function delta(a, b, key) {
  if (!a || !b) return ''
  const diff = (b[key] || 0) - (a[key] || 0)
  return diff === 0 ? '' : diff > 0 ? `+${key === 'avg_ms' ? ms(diff) : diff}` : `${key === 'avg_ms' ? '-' + ms(-diff) : diff}`
}
</script>

<template>
  <div class="page">
    <header>
      <h1>Compare sessions</h1>
      <p class="muted">See what changed between two captures of a server: its tools, and how
        each call behaved.</p>
      <div class="pickers">
        <label>Before
          <select v-model="before" class="field">
            <option v-for="s in sessions" :key="s.id" :value="s.id">{{ label(s) }}</option>
          </select>
        </label>
        <label>After
          <select v-model="after" class="field">
            <option v-for="s in sessions" :key="s.id" :value="s.id">{{ label(s) }}</option>
          </select>
        </label>
      </div>
    </header>
    <p v-if="error" class="err">{{ error }}</p>
    <div v-else-if="sessions.length < 2" class="empty">
      <h2>Two sessions are needed</h2>
      <p>Restart your client or reconnect the server to capture a second session.</p>
    </div>
    <template v-else-if="report">
      <section>
        <h2>Tools</h2>
        <p v-if="!report.tools" class="faint">One of the sessions never listed its tools.</p>
        <template v-else>
          <p class="muted">Definitions went from ≈{{ tokens(report.tools.definition_tokens.before) }}
            to ≈{{ tokens(report.tools.definition_tokens.after) }} tokens per turn.</p>
          <ul class="drift">
            <li v-for="t in report.tools.added" :key="'a' + t" class="added">Added <code>{{ t }}</code></li>
            <li v-for="t in report.tools.removed" :key="'r' + t" class="removed">Removed <code>{{ t }}</code></li>
            <li v-for="t in report.tools.changed" :key="'c' + t.name" class="changed">
              Changed <code>{{ t.name }}</code>: {{ t.fields.join(', ') }}
              <span class="faint">({{ t.token_delta >= 0 ? '+' : '' }}{{ t.token_delta }} tokens)</span>
            </li>
            <li v-if="!report.tools.added.length && !report.tools.removed.length && !report.tools.changed.length"
                class="faint">No tool changes.</li>
          </ul>
        </template>
      </section>
      <section>
        <h2>Calls</h2>
        <table class="grid">
          <thead><tr><th>Call</th><th class="num">Before</th><th class="num">After</th>
            <th class="num">Errors</th><th class="num">Avg time</th></tr></thead>
          <tbody>
            <tr v-for="c in report.calls" :key="c.call">
              <td class="mono">{{ c.call }}</td>
              <td class="num">{{ c.before?.calls ?? 0 }}</td>
              <td class="num">{{ c.after?.calls ?? 0 }}</td>
              <td class="num">{{ c.before?.errors ?? 0 }} / {{ c.after?.errors ?? 0 }}</td>
              <td class="num mono">{{ ms(c.after?.avg_ms ?? c.before?.avg_ms) }}
                <span class="faint">{{ delta(c.before, c.after, 'avg_ms') }}</span></td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page { overflow: auto; height: 100%; padding: 16px 18px 32px; }
.page > * { max-width: 980px; }
h1 { font-size: 19px; font-weight: 600; margin: 0 0 4px; }
h2 { font-size: 14px; font-weight: 600; margin: 22px 0 8px; }
header p { margin: 0 0 12px; }
.pickers { display: flex; gap: 16px; flex-wrap: wrap; }
.pickers label { display: flex; flex-direction: column; gap: 4px; color: var(--muted); font-size: 13px; }
.pickers select { min-width: 320px; color: var(--text); }
.drift { list-style: none; padding: 0; margin: 0; }
.drift li { padding: 3px 0; }
.added { color: var(--ok); }
.removed { color: var(--error); }
.changed { color: var(--hung); }
.err { color: var(--error); }
</style>
