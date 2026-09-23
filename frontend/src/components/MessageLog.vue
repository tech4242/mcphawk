<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'
import JsonTree from './JsonTree.vue'

const props = defineProps({ sessionId: { type: String, required: true } })
const rows = ref([])
const open = ref({})

onMounted(async () => { rows.value = await api.sessionMessages(props.sessionId) })

async function toggle(row) {
  if (open.value[row.id]) { delete open.value[row.id]; return }
  open.value[row.id] = (await api.message(row.id)).body
}
</script>

<template>
  <div class="log">
    <p class="faint">Every frame on the wire in order, including notifications and anything
      that was not valid JSON-RPC.</p>
    <table class="grid">
      <thead><tr><th>#</th><th>Direction</th><th>Kind</th><th>Method</th><th class="num">Bytes</th><th>Note</th></tr></thead>
      <tbody>
        <template v-for="row in rows" :key="row.id">
          <tr class="row" :class="row.kind" tabindex="0" @click="toggle(row)" @keydown.enter="toggle(row)">
            <td class="faint mono">{{ row.id }}</td>
            <td :class="row.direction">{{ row.direction === 'c2s' ? 'client to server' : 'server to client' }}</td>
            <td>{{ row.kind }}</td>
            <td class="mono">{{ row.method || (row.rpc_id ? `id ${row.rpc_id}` : '') }}</td>
            <td class="num mono">{{ row.size }}</td>
            <td class="faint">{{ row.note }}</td>
          </tr>
          <tr v-if="open[row.id] !== undefined"><td colspan="6"><JsonTree :value="open[row.id]" :depth="2" /></td></tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.log { padding: 10px 18px; }
.row { cursor: pointer; }
.row:hover { background: var(--raised); }
.c2s { color: var(--c2s); }
.s2c { color: var(--s2c); }
.invalid td { color: var(--error); }
</style>
