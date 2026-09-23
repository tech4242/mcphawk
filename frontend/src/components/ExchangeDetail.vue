<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import { call, ms, tokens, when } from '../format.js'
import StatusBadge from './StatusBadge.vue'
import JsonTree from './JsonTree.vue'
import ContentBlocks from './ContentBlocks.vue'

const props = defineProps({ id: { type: Number, required: true } })
const emit = defineEmits(['close'])
const router = useRouter()

const exchange = ref(null)
const error = ref(null)
const view = ref(null)
const copied = ref(false)

const replaying = ref(false)
const replayText = ref('')
const replayError = ref(null)
const replayResult = ref(null)
const sending = ref(false)

onMounted(async () => {
  try {
    exchange.value = await api.exchange(props.id)
    view.value = content.value ? 'result' : 'response'
  } catch (e) {
    error.value = e.message
  }
})

const request = computed(() => exchange.value?.request?.body)
const response = computed(() => exchange.value?.response?.body)
const result = computed(() => response.value?.result)
const content = computed(() => (Array.isArray(result.value?.content) ? result.value.content : null))
const headers = computed(() => exchange.value?.request?.headers)
const views = computed(() => [
  ...(content.value ? [['result', 'Result']] : []),
  ['response', 'Response'],
  ['request', 'Request'],
  ...(headers.value ? [['headers', 'Headers']] : []),
])
const canReplay = computed(() => exchange.value?.initiator === 'client'
  && ['stdio', 'streamable_http'].includes(exchange.value?.session?.transport))

async function copyLink() {
  const base = window.location.origin
  await navigator.clipboard.writeText(`${base}/x/${props.id}`)
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}

function startReplay() {
  replaying.value = true
  replayError.value = null
  replayResult.value = null
  replayText.value = JSON.stringify(request.value?.params ?? {}, null, 2)
}

async function sendReplay() {
  let params
  try {
    params = JSON.parse(replayText.value)
  } catch (e) {
    replayError.value = `The params are not valid JSON: ${e.message}`
    return
  }
  sending.value = true
  replayError.value = null
  try {
    replayResult.value = await api.replay(props.id, params)
  } catch (e) {
    replayError.value = e.message
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <aside class="detail" aria-label="Call details">
    <div v-if="error" class="empty"><h2>Call not found</h2><p>{{ error }}</p></div>
    <template v-else-if="exchange">
      <header>
        <div class="row">
          <code class="call">{{ call(exchange) }}</code>
          <button class="close" aria-label="Close details" @click="emit('close')">×</button>
        </div>
        <div class="facts">
          <StatusBadge :status="exchange.status" />
          <span>{{ ms(exchange.duration_ms) }}</span>
          <span title="Estimated tokens in the request / result">
            ≈{{ tokens(exchange.request_tokens) }} in, ≈{{ tokens(exchange.response_tokens) }} out
          </span>
          <router-link v-if="exchange.session" :to="`/s/${exchange.session_id}?x=${exchange.id}`"
                       class="muted">{{ exchange.session.display_name }}</router-link>
          <span class="faint">{{ when(exchange.started_at) }}</span>
        </div>
        <p v-if="exchange.error_message" class="error-msg">
          <template v-if="exchange.error_code !== null">[{{ exchange.error_code }}] </template>
          {{ exchange.error_message }}
        </p>
        <div class="actions">
          <button class="btn" @click="copyLink">{{ copied ? 'Link copied' : 'Copy link' }}</button>
          <button v-if="canReplay" class="btn" @click="startReplay">Replay…</button>
        </div>
      </header>

      <section v-if="exchange.chain.length" class="chain">
        <h3>Multi round-trip</h3>
        <ol>
          <li v-for="step in exchange.chain" :key="step.id" :class="{ current: step.id === exchange.id }">
            <a href="#" @click.prevent="router.replace({ query: { ...$route.query, x: step.id } })">
              {{ step.status === 'input_required' ? 'Server asked for input' : 'Completed' }}
            </a>
            <span class="faint"> {{ ms(step.duration_ms) }}</span>
          </li>
        </ol>
      </section>

      <section v-if="replaying" class="replay">
        <h3>Replay with these params</h3>
        <p class="faint">Sends a real request to the server in a new connection. Tools with side
          effects will run again.</p>
        <textarea v-model="replayText" class="field mono" rows="8" spellcheck="false"
                  aria-label="Request params (JSON)" />
        <div class="actions">
          <button class="btn primary" :disabled="sending" @click="sendReplay">
            {{ sending ? 'Replaying…' : 'Send replay' }}
          </button>
          <button class="btn" @click="replaying = false">Cancel</button>
        </div>
        <p v-if="replayError" class="error-msg">{{ replayError }}</p>
        <div v-if="replayResult" class="replay-result">
          <p>Replayed: <StatusBadge v-if="replayResult.status" :status="replayResult.status" />
            <router-link :to="`/s/${replayResult.session_id}?x=${replayResult.exchange_id}`">
              Open the replay</router-link>
            <router-link class="muted" :to="`/compare?before=${exchange.session_id}&after=${replayResult.session_id}`">
              Compare with original</router-link>
          </p>
          <JsonTree :value="replayResult.response" :depth="2" />
        </div>
      </section>

      <nav class="views" role="tablist">
        <button v-for="[name, label] in views" :key="name" role="tab" :aria-selected="view === name"
                :class="{ active: view === name }" @click="view = name">{{ label }}</button>
      </nav>
      <section class="payload">
        <ContentBlocks v-if="view === 'result'" :blocks="content" :structured="result.structuredContent" />
        <template v-else-if="view === 'response'">
          <JsonTree v-if="response" :value="response" :depth="3" />
          <p v-else class="faint">No response yet.</p>
        </template>
        <JsonTree v-else-if="view === 'request'" :value="request" :depth="3" />
        <table v-else-if="view === 'headers'" class="grid headers">
          <tr v-for="(value, name) in headers" :key="name">
            <th>{{ name }}</th><td class="mono">{{ value }}</td>
          </tr>
        </table>
      </section>
    </template>
  </aside>
</template>

<style scoped>
.detail {
  border-left: 1px solid var(--line); background: var(--surface);
  overflow-y: auto; min-height: 0; height: 100%;
}
header { padding: 14px 16px 10px; border-bottom: 1px solid var(--line); }
.row { display: flex; align-items: flex-start; gap: 8px; }
.call { font-size: 14px; word-break: break-all; flex: 1; }
.close {
  background: none; border: 0; font-size: 20px; line-height: 1; cursor: pointer;
  color: var(--muted); padding: 0 4px;
}
.facts { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-top: 8px; font-size: 13px; }
.error-msg { color: var(--error); margin: 8px 0 0; white-space: pre-wrap; }
.actions { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
h3 { font-size: 13px; font-weight: 600; margin: 0 0 6px; }
.chain, .replay { padding: 12px 16px; border-bottom: 1px solid var(--line); }
.chain ol { margin: 0; padding-left: 20px; }
.chain li.current a { font-weight: 600; text-decoration: none; }
.replay textarea { width: 100%; resize: vertical; }
.replay-result { margin-top: 10px; }
.replay-result p { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.views { display: flex; gap: 2px; padding: 0 12px; border-bottom: 1px solid var(--line); }
.views button {
  background: none; border: 0; border-bottom: 2px solid transparent;
  padding: 7px 8px; color: var(--muted); cursor: pointer;
}
.views button.active { color: var(--text); border-bottom-color: var(--brand); }
.payload { padding: 12px 16px 24px; }
.headers th { width: 35%; font-family: var(--mono); font-weight: 400; }
.headers td { word-break: break-all; }
</style>
