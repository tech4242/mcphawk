import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import './live.js'

import HomeView from './views/HomeView.vue'
import TrafficView from './views/TrafficView.vue'
import ExchangeRedirect from './views/ExchangeRedirect.vue'
import ProblemsView from './views/ProblemsView.vue'
import CostView from './views/CostView.vue'
import CompareView from './views/CompareView.vue'
import SetupView from './views/SetupView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/r/:key', component: TrafficView, props: (r) => ({ runKey: r.params.key }) },
    { path: '/s/:id', component: TrafficView, props: (r) => ({ sessionId: r.params.id }) },
    { path: '/x/:id', component: ExchangeRedirect, props: true },
    { path: '/problems', component: ProblemsView },
    { path: '/cost', component: CostView },
    { path: '/compare', component: CompareView },
    { path: '/setup', component: SetupView },
  ],
})

createApp(App).use(router).mount('#app')
