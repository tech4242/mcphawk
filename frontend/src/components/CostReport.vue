<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '../api.js'
import { tokens } from '../format.js'

const props = defineProps({ scope: { type: Object, default: () => ({}) } })
const report = ref(null)
const error = ref(null)
const open = ref(null)

watch(() => props.scope, async () => {
  try {
    report.value = await api.cost(props.scope)
    open.value = report.value.servers[0]?.server ?? null
  } catch (e) {
    error.value = e.message
  }
}, { immediate: true })

const maxFixed = computed(() => Math.max(1, ...(report.value?.servers || [])
  .map((s) => s.fixed_tokens_per_turn)))
</script>

<template>
  <div class="cost">
    <p v-if="error" class="error">{{ error }}</p>
    <div v-else-if="report && !report.servers.length" class="empty">
      <h2>No servers captured yet</h2>
      <p>Context cost appears once a client has listed a server's tools.</p>
    </div>
    <template v-else-if="report">
      <div class="headline">
        <div>
          <strong>≈{{ tokens(report.fixed_tokens_per_turn) }}</strong>
          <span class="muted">tokens of tool definitions sent with every model turn</span>
        </div>
        <div>
          <strong>≈{{ tokens(report.result_tokens) }}</strong>
          <span class="muted">tokens of tool results added to the conversation</span>
        </div>
      </div>
      <p class="faint note">Estimates: {{ report.estimate }}.</p>

      <section v-if="report.findings.length" class="findings">
        <h2>Worth a look</h2>
        <ul><li v-for="f in report.findings" :key="f">{{ f }}</li></ul>
      </section>

      <section class="servers">
        <h2>Per server</h2>
        <div v-for="s in report.servers" :key="s.server" class="server">
          <button class="server-row" :aria-expanded="open === s.server"
                  @click="open = open === s.server ? null : s.server">
            <span class="name">{{ s.server }}</span>
            <span class="meter"><span :style="{ width: `${(s.fixed_tokens_per_turn / maxFixed) * 100}%` }" /></span>
            <span class="mono num">≈{{ tokens(s.fixed_tokens_per_turn) }}/turn</span>
            <span class="faint">{{ s.tool_count }} tools</span>
          </button>
          <div v-if="open === s.server" class="breakdown">
            <table class="grid">
              <thead>
                <tr><th>Tool</th><th class="num">Definition</th><th>Description vs schema</th>
                  <th class="num">Calls</th><th class="num">Avg result</th></tr>
              </thead>
              <tbody>
                <tr v-for="d in s.definitions" :key="d.name"
                    :class="{ unused: s.unused_tools.includes(d.name) && s.calls.length }">
                  <td class="mono">{{ d.name }}</td>
                  <td class="num mono">≈{{ tokens(d.total) }}</td>
                  <td>
                    <span class="split" :title="`description ≈${d.description}, schema ≈${d.schema}`">
                      <span class="desc" :style="{ flexGrow: d.description }" />
                      <span class="schema" :style="{ flexGrow: d.schema }" />
                    </span>
                  </td>
                  <td class="num">{{ s.calls.find((c) => c.tool === d.name)?.calls ?? 0 }}</td>
                  <td class="num mono">
                    {{ tokens(s.calls.find((c) => c.tool === d.name)?.avg_result_tokens ?? 0) }}
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-if="s.instructions_tokens" class="faint">
              Server instructions add ≈{{ tokens(s.instructions_tokens) }} tokens.</p>
          </div>
        </div>
      </section>

      <section v-if="report.heaviest_results.length" class="heaviest">
        <h2>Largest tool results</h2>
        <table class="grid">
          <tbody>
            <tr v-for="h in report.heaviest_results" :key="h.exchange_id">
              <td><router-link :to="`/s/${h.session_id}?x=${h.exchange_id}`" class="mono">{{ h.tool }}</router-link></td>
              <td class="faint">{{ h.server }}</td>
              <td class="num mono">≈{{ tokens(h.tokens) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.cost { padding: 14px 18px 32px; max-width: 980px; }
.headline { display: flex; gap: 40px; flex-wrap: wrap; }
.headline div { display: flex; flex-direction: column; }
.headline strong { font-size: 28px; font-weight: 600; font-variant-numeric: tabular-nums; }
.note { font-size: 12.5px; margin: 6px 0 18px; }
h2 { font-size: 14px; font-weight: 600; margin: 18px 0 8px; }
.findings ul { margin: 0; padding-left: 18px; color: var(--hung); }
.findings li span, .findings li { line-height: 1.6; }
.server { border-bottom: 1px solid color-mix(in srgb, var(--line) 50%, transparent); }
.server-row {
  display: grid; grid-template-columns: 200px 1fr 110px 70px; gap: 12px; align-items: center;
  width: 100%; background: none; border: 0; padding: 8px 0; cursor: pointer; text-align: left;
}
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meter { height: 8px; background: var(--raised); border-radius: 4px; overflow: hidden; }
.meter span { display: block; height: 100%; background: var(--s2c); }
.breakdown { padding: 4px 0 14px; }
.split { display: flex; width: 120px; height: 8px; border-radius: 4px; overflow: hidden; background: var(--raised); }
.desc { background: var(--c2s); }
.schema { background: var(--input); }
tr.unused td:first-child::after { content: ' never called'; color: var(--faint); font-family: var(--sans); font-size: 12px; }
.error { color: var(--error); }
@media (max-width: 700px) { .server-row { grid-template-columns: 1fr 90px; } .meter, .server-row .faint { display: none; } }
</style>
