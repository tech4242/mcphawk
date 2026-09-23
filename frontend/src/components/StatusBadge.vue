<script setup>
import { STATUS_LABELS } from '../format.js'

defineProps({ status: { type: String, required: true } })
</script>

<template>
  <span class="badge" :class="status">{{ STATUS_LABELS[status] || status }}</span>
</template>

<style scoped>
.badge {
  display: inline-block; font-size: 12px; padding: 0 7px; border-radius: 10px;
  border: 1px solid currentColor; line-height: 18px;
  color: var(--muted);
}
.ok { color: var(--ok); border-color: transparent; padding-left: 0; }
.error { color: var(--error); }
.tool_error { color: var(--tool-error); }
.input_required { color: var(--input); }
.pending { color: var(--pending); }
.hung { color: var(--hung); }
.abandoned, .cancelled { color: var(--faint); }
</style>
