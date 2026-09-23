<script setup>
import { ref, watch } from 'vue'
import { api } from '../api.js'
import { live } from '../live.js'

const props = defineProps({ scope: { type: Object, default: () => ({}) } })
const severity = ref('warning')
const report = ref(null)
const error = ref(null)

async function load() {
  try {
    report.value = await api.problems({ ...props.scope, min_severity: severity.value })
    error.value = null
  } catch (e) {
    error.value = e.message
  }
}
watch(severity, load, { immediate: true })
watch(() => live.tick, () => setTimeout(load, 400))

function link(problem) {
  const base = `/s/${problem.session_id}`
  return problem.exchange_id ? `${base}?x=${problem.exchange_id}` : base
}
</script>

<template>
  <div class="problems">
    <div class="bar">
      <p v-if="report" class="muted">
        {{ report.total }} problem{{ report.total === 1 ? '' : 's' }} across
        {{ report.sessions_checked }} session{{ report.sessions_checked === 1 ? '' : 's' }}
      </p>
      <select v-model="severity" class="field" aria-label="Minimum severity">
        <option value="error">Errors only</option>
        <option value="warning">Errors and warnings</option>
        <option value="info">Everything, including spec notes</option>
      </select>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div v-else-if="report && !report.problems.length" class="empty">
      <h2>Nothing went wrong here</h2>
      <p>No failed, hung or repeated calls, and no spec issues at this level.</p>
    </div>
    <ul v-else-if="report">
      <li v-for="(p, i) in report.problems" :key="i" :class="p.severity">
        <router-link :to="link(p)">
          <span class="sev" :title="p.severity" />
          <span class="title">{{ p.title }}</span>
          <span v-if="p.count > 1" class="count">{{ p.count }}×</span>
          <span class="server faint">{{ p.server }}</span>
        </router-link>
        <p v-if="p.detail" class="detail muted">{{ p.detail }}</p>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.problems { padding: 12px 18px; max-width: 980px; }
.bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
ul { list-style: none; padding: 0; margin: 8px 0; }
li { padding: 8px 0; border-bottom: 1px solid color-mix(in srgb, var(--line) 50%, transparent); }
li a { display: flex; align-items: baseline; gap: 10px; text-decoration: none; }
li a:hover .title { text-decoration: underline; }
.sev { width: 9px; height: 9px; border-radius: 50%; flex: none; align-self: center; background: var(--faint); }
.error .sev { background: var(--error); }
.warning .sev { background: var(--hung); }
.title { font-family: var(--mono); font-size: 13px; }
.count { color: var(--muted); font-size: 12.5px; }
.server { margin-left: auto; font-size: 12.5px; }
.detail { margin: 2px 0 0 19px; font-size: 13px; white-space: pre-wrap; word-break: break-word; }
.error { color: var(--error); }
</style>
