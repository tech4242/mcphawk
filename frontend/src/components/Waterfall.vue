<script setup>
import { computed, nextTick, watch } from 'vue'
import { ms, tokens, STATUS_LABELS } from '../format.js'
import StatusBadge from './StatusBadge.vue'

const props = defineProps({
  exchanges: { type: Array, required: true },
  colors: { type: Object, required: true },
  names: { type: Object, required: true },
  selected: Number,
  multi: Boolean,
})
const emit = defineEmits(['select'])

const span = computed(() => {
  if (!props.exchanges.length) return { start: 0, total: 1 }
  const start = Math.min(...props.exchanges.map((e) => e.started_at))
  const end = Math.max(...props.exchanges.map((e) =>
    e.started_at + (e.duration_ms || 0) / 1000))
  return { start, total: Math.max(end - start, 0.001) }
})

function bar(exchange) {
  const left = ((exchange.started_at - span.value.start) / span.value.total) * 100
  const width = (((exchange.duration_ms || 0) / 1000) / span.value.total) * 100
  return {
    left: `${Math.min(left, 99.6)}%`,
    width: `max(3px, ${Math.min(width, 100 - left)}%)`,
    background: props.colors[exchange.session_id],
  }
}

const maxTokens = computed(() => Math.max(1, ...props.exchanges.map((e) => e.response_tokens)))

function onKey(event, index) {
  const step = { ArrowDown: 1, ArrowUp: -1 }[event.key]
  if (!step) return
  event.preventDefault()
  const next = props.exchanges[index + step]
  if (next) emit('select', next.id)
}

watch(() => props.selected, async (id) => {
  await nextTick()
  document.querySelector(`[data-exchange="${id}"]`)?.focus({ preventScroll: false })
})
</script>

<template>
  <div v-if="!exchanges.length" class="empty">
    <h2>No calls match</h2>
    <p>Clear the filter or status to see every call in this run.</p>
  </div>
  <table v-else class="waterfall">
    <thead>
      <tr>
        <th v-if="multi" class="server-col">Server</th>
        <th>Call</th>
        <th>Status</th>
        <th class="num">Time</th>
        <th class="num" title="Estimated tokens the result adds to the model's context">Result</th>
        <th class="bar-col" aria-label="Timeline" />
      </tr>
    </thead>
    <tbody>
      <tr v-for="(e, index) in exchanges" :key="e.id" :data-exchange="e.id" tabindex="0"
          :class="{ selected: e.id === selected, child: e.parent_id, problem: !['ok', 'input_required', 'pending'].includes(e.status) }"
          :aria-selected="e.id === selected"
          @click="emit('select', e.id)" @keydown.enter="emit('select', e.id)"
          @keydown="onKey($event, index)">
        <td v-if="multi" class="server-col">
          <span class="swatch" :style="{ background: colors[e.session_id] }" />
          {{ names[e.session_id] }}
        </td>
        <td class="call">
          <span v-if="e.parent_id" class="retry" title="Retry after the server asked for input">retry</span>
          <span v-if="e.initiator === 'server'" class="from-server" title="Sent by the server to the client">server asks</span>
          <code>{{ e.method }}</code>
          <code v-if="e.target" class="target">{{ e.target }}</code>
        </td>
        <td><StatusBadge :status="e.status" :title="e.error_message || STATUS_LABELS[e.status]" /></td>
        <td class="num mono">{{ ms(e.duration_ms) }}</td>
        <td class="num mono tok">
          <span class="tok-bar" :style="{ width: `${(e.response_tokens / maxTokens) * 100}%` }" />
          <span class="tok-val">{{ tokens(e.response_tokens) }}</span>
        </td>
        <td class="bar-col">
          <span class="track"><span class="bar" :class="e.status" :style="bar(e)" /></span>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.waterfall { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th {
  position: sticky; top: 0; z-index: 1; background: var(--dusk);
  text-align: left; font-weight: 500; color: var(--muted); font-size: 12.5px;
  padding: 7px 10px; border-bottom: 1px solid var(--line);
}
thead th.num { text-align: right; }
tbody tr { cursor: pointer; }
tbody td {
  padding: 4px 10px; border-bottom: 1px solid color-mix(in srgb, var(--line) 45%, transparent);
  white-space: nowrap;
}
tbody tr:hover { background: color-mix(in srgb, var(--raised) 60%, transparent); }
tbody tr.selected { background: var(--raised); box-shadow: inset 3px 0 0 var(--brand); }
tbody tr.problem .call code:first-of-type { color: var(--error); }
.server-col { max-width: 160px; overflow: hidden; text-overflow: ellipsis; }
.swatch { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 6px; }
.call { max-width: 0; width: 38%; overflow: hidden; text-overflow: ellipsis; }
.call code { font-size: 12.5px; }
.target { color: var(--s2c); margin-left: 6px; }
tr.child .call { padding-left: 26px; }
.retry, .from-server {
  font-size: 11.5px; color: var(--input); margin-right: 6px;
  border: 1px solid color-mix(in srgb, var(--input) 45%, transparent);
  border-radius: 4px; padding: 0 4px;
}
.from-server { color: var(--s2c); border-color: color-mix(in srgb, var(--s2c) 45%, transparent); }
.tok { position: relative; width: 76px; }
.tok-bar {
  position: absolute; right: 8px; top: 50%; height: 14px; transform: translateY(-50%);
  background: color-mix(in srgb, var(--s2c) 18%, transparent); border-radius: 2px;
  max-width: calc(100% - 16px);
}
.tok-val { position: relative; }
.bar-col { width: 34%; min-width: 160px; }
.track { display: block; position: relative; height: 12px; }
.bar {
  position: absolute; top: 2px; height: 8px; border-radius: 2px; opacity: .85;
}
.bar.error, .bar.tool_error { outline: 2px solid var(--error); outline-offset: 0; }
.bar.hung, .bar.pending {
  background-image: repeating-linear-gradient(90deg, transparent 0 4px, var(--dusk) 4px 6px) !important;
  outline: 1px solid var(--hung);
}
.bar.hung { animation: pulse 1.4s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .45; } }
</style>
