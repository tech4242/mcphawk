<script setup>
import JsonTree from './JsonTree.vue'

defineProps({ blocks: { type: Array, required: true }, structured: { default: undefined } })

function dataUrl(block) {
  return `data:${block.mimeType || 'application/octet-stream'};base64,${block.data}`
}
</script>

<template>
  <div class="blocks">
    <p v-if="!blocks.length" class="faint">The tool returned no content.</p>
    <div v-for="(block, i) in blocks" :key="i" class="block">
      <pre v-if="block.type === 'text'" class="text">{{ block.text }}</pre>
      <img v-else-if="block.type === 'image'" :src="dataUrl(block)" alt="Image returned by the tool" />
      <audio v-else-if="block.type === 'audio'" :src="dataUrl(block)" controls />
      <div v-else-if="block.type === 'resource'" class="resource">
        <code class="uri">{{ block.resource?.uri }}</code>
        <pre v-if="block.resource?.text" class="text">{{ block.resource.text }}</pre>
        <p v-else class="faint">Binary resource ({{ block.resource?.mimeType || 'unknown type' }})</p>
      </div>
      <div v-else-if="block.type === 'resource_link'" class="resource">
        <span class="faint">Link to</span> <code class="uri">{{ block.uri }}</code>
        <span v-if="block.name"> {{ block.name }}</span>
      </div>
      <JsonTree v-else :value="block" :depth="2" />
    </div>
    <div v-if="structured !== undefined" class="block">
      <h3>Structured content</h3>
      <JsonTree :value="structured" :depth="3" />
    </div>
  </div>
</template>

<style scoped>
.block + .block { margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--line); }
.text {
  margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12.5px;
  max-height: 60vh; overflow: auto;
}
img { max-width: 100%; border-radius: var(--radius); border: 1px solid var(--line); }
.uri { color: var(--s2c); }
h3 { font-size: 13px; font-weight: 600; margin: 0 0 6px; }
</style>
