<script setup>
import { computed, ref } from 'vue'

defineOptions({ name: 'JsonTree' })
const props = defineProps({
  value: { required: true },
  name: { type: [String, Number], default: null },
  depth: { type: Number, default: 2 },
  level: { type: Number, default: 0 },
})

const LONG = 400
const isObject = computed(() => props.value !== null && typeof props.value === 'object')
const isArray = computed(() => Array.isArray(props.value))
const entries = computed(() => (isObject.value ? Object.entries(props.value) : []))
const open = ref(props.level < props.depth)
const full = ref(false)

const kind = computed(() => (props.value === null ? 'null' : typeof props.value))
const text = computed(() => {
  if (typeof props.value !== 'string') return JSON.stringify(props.value)
  const quoted = JSON.stringify(props.value)
  return full.value || quoted.length <= LONG ? quoted : `${quoted.slice(0, LONG)}…`
})
const summary = computed(() => (isArray.value
  ? `[${props.value.length}]`
  : `{${entries.value.length}}`))
</script>

<template>
  <div class="node" :class="{ root: level === 0 }">
    <template v-if="isObject">
      <button class="toggle" :aria-expanded="open" @click="open = !open">
        <span class="caret">{{ open ? '▾' : '▸' }}</span>
        <span v-if="name !== null" class="key">{{ name }}</span>
        <span class="summary">{{ summary }}</span>
      </button>
      <div v-if="open" class="children">
        <JsonTree v-for="[key, child] in entries" :key="key" :name="isArray ? Number(key) : key"
                  :value="child" :depth="depth" :level="level + 1" />
      </div>
    </template>
    <div v-else class="leaf">
      <span v-if="name !== null" class="key">{{ name }}</span>
      <span class="value" :class="kind">{{ text }}</span>
      <button v-if="kind === 'string' && JSON.stringify(value).length > LONG" class="more"
              @click="full = !full">{{ full ? 'less' : `${value.length} chars` }}</button>
    </div>
  </div>
</template>

<style scoped>
.node { font-family: var(--mono); font-size: 12.5px; line-height: 1.6; }
.children { padding-left: 16px; border-left: 1px solid color-mix(in srgb, var(--line) 60%, transparent); margin-left: 5px; }
.toggle { background: none; border: 0; padding: 0; cursor: pointer; display: inline-flex; gap: 6px; text-align: left; }
.caret { color: var(--faint); width: 10px; }
.key { color: var(--c2s); }
.key::after { content: ':'; color: var(--faint); }
.leaf { display: flex; gap: 6px; align-items: baseline; padding-left: 16px; }
.root > .leaf { padding-left: 0; }
.value { white-space: pre-wrap; word-break: break-word; }
.string { color: var(--s2c); }
.number { color: var(--input); }
.boolean, .null { color: var(--ok); }
.summary { color: var(--faint); }
.more { background: none; border: 0; color: var(--focus); cursor: pointer; font-size: 11.5px; flex: none; }
</style>
