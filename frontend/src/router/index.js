import { createRouter, createWebHistory } from 'vue-router'
import LogView from '@/views/LogView.vue'
import AnalyticsView from '@/views/AnalyticsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'logs',
      component: LogView
    },
    {
      path: '/analytics',
      name: 'analytics',
      component: AnalyticsView
    }
  ]
})

export default router