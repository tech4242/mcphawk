<template>
  <div class="w-full">
    <div class="mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
        Transport Type Distribution
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
        Breakdown of MCP traffic by transport protocol
      </p>
    </div>
    <div v-if="loading" class="flex items-center justify-center" style="height: 250px;">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
    <div v-else-if="!chartData" class="flex items-center justify-center" style="height: 250px;">
      <span class="text-gray-500 dark:text-gray-400">No data available</span>
    </div>
    <div v-else class="relative" style="height: 250px;">
      <Doughnut :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAnalyticsStore } from '@/stores/analytics'
import { Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(ArcElement, Tooltip, Legend)

const analyticsStore = useAnalyticsStore()

const loading = computed(() => analyticsStore.loading.transport)

const transportColors = {
  streamable_http: 'rgb(59, 130, 246)',
  http_sse: 'rgb(34, 197, 94)',
  stdio: 'rgb(168, 85, 247)',
  unknown: 'rgb(156, 163, 175)'
}

const chartData = computed(() => {
  if (!analyticsStore.transportDistribution?.distribution) return null
  
  const distribution = analyticsStore.transportDistribution.distribution
  
  return {
    labels: distribution.map(d => {
      const label = d.transport_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())
      return `${label} (${d.percentage.toFixed(1)}%)`
    }),
    datasets: [{
      data: distribution.map(d => d.count),
      backgroundColor: distribution.map(d => transportColors[d.transport_type] || transportColors.unknown),
      borderWidth: 0
    }]
  }
})

const isDark = computed(() => document.documentElement.classList.contains('dark'))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        color: isDark.value ? '#e5e7eb' : '#374151',
        padding: 15,
        usePointStyle: true
      }
    },
    tooltip: {
      backgroundColor: isDark.value ? '#1f2937' : '#ffffff',
      titleColor: isDark.value ? '#e5e7eb' : '#111827',
      bodyColor: isDark.value ? '#d1d5db' : '#374151',
      borderColor: isDark.value ? '#374151' : '#e5e7eb',
      borderWidth: 1,
      callbacks: {
        label: function(context) {
          const label = context.label || ''
          const value = context.parsed || 0
          return `${label}: ${value} messages`
        }
      }
    }
  }
}))
</script>