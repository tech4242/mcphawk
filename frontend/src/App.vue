<script setup>
import RunRail from './components/RunRail.vue'
import { live } from './live.js'
</script>

<template>
  <div class="shell">
    <aside class="rail">
      <router-link to="/" class="brand" aria-label="MCPHawk home">
        <img src="/mcphawk_logo.png" alt="MCPHawk" width="923" height="507" />
        <span class="dot" :class="{ on: live.connected }" role="status"
              :title="live.connected ? 'Live: new traffic appears automatically' : 'Reconnecting'" />
      </router-link>
      <nav class="nav">
        <router-link to="/problems">Problems</router-link>
        <router-link to="/cost">Context cost</router-link>
        <router-link to="/compare">Compare</router-link>
        <router-link to="/setup">Setup</router-link>
      </nav>
      <RunRail />
    </aside>
    <main class="main">
      <router-view :key="$route.path" />
    </main>
  </div>
</template>

<style scoped>
.shell { display: grid; grid-template-columns: 248px 1fr; height: 100%; }
.rail {
  border-right: 1px solid var(--line);
  display: flex; flex-direction: column; min-height: 0;
  background: color-mix(in srgb, var(--surface) 55%, var(--dusk));
}
.brand { position: relative; display: block; padding: 14px 20px 12px; }
.brand img { display: block; width: 100%; max-width: 190px; height: auto; margin: 0 auto; }
.dot {
  position: absolute; top: 12px; right: 12px;
  width: 7px; height: 7px; border-radius: 50%; background: var(--faint);
}
.dot.on { background: var(--ok); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 25%, transparent); }
.nav { display: flex; flex-direction: column; padding: 0 8px 10px; border-bottom: 1px solid var(--line); }
.nav a { padding: 5px 8px; border-radius: var(--radius); text-decoration: none; color: var(--muted); }
.nav a:hover { color: var(--text); background: var(--raised); }
.nav a.router-link-active { color: var(--text); background: var(--raised); }
.main { min-width: 0; min-height: 0; overflow: hidden; display: flex; flex-direction: column; }
@media (max-width: 760px) {
  .shell { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
  .rail { max-height: 40vh; border-right: 0; border-bottom: 1px solid var(--line); }
  .brand img { max-width: 120px; margin: 0; }
}
</style>
