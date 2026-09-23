<script setup>
import CostReport from '../components/CostReport.vue'
</script>

<template>
  <div class="page">
    <header>
      <h1>Context cost</h1>
      <p class="muted">What your MCP servers put into the model's context window, based on the
        latest tool list each one sent.</p>
    </header>
    <CostReport />
  </div>
</template>

<style scoped>
.page { overflow: auto; height: 100%; }
header { padding: 16px 18px 0; max-width: 72ch; }
h1 { font-size: 19px; font-weight: 600; margin: 0 0 4px; }
header p { margin: 0; }
</style>
