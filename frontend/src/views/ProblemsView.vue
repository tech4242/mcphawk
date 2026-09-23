<script setup>
import ProblemList from '../components/ProblemList.vue'
</script>

<template>
  <div class="page">
    <header><h1>Problems</h1><p class="muted">Across the 200 most recent sessions.</p></header>
    <ProblemList />
  </div>
</template>

<style scoped>
.page { overflow: auto; height: 100%; }
header { padding: 16px 18px 0; }
h1 { font-size: 19px; font-weight: 600; margin: 0 0 4px; }
header p { margin: 0; }
</style>
