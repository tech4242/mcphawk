<template>
  <div class="w-full">
    <div class="mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
        Message Type Breakdown
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
        Distribution of message types in captured traffic
      </p>
    </div>
    <div v-if="loading" class="flex items-center justify-center" style="height: 250px;">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
    <div v-else-if="!chartData" class="flex items-center justify-center" style="height: 250px;">
      <span class="text-gray-500 dark:text-gray-400">No data available</span>
    </div>
    <div v-else class="relative" style="height: 250px;">
      <Bar :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAnalyticsStore } from '@/stores/analytics'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

const analyticsStore = useAnalyticsStore()

const loading = computed(() => analyticsStore.loading.messageTypes)

const messageTypeColors = {
  request: 'rgb(59, 130, 246)',
  response: 'rgb(34, 197, 94)',
  notification: 'rgb(168, 85, 247)',
  error: 'rgb(239, 68, 68)',
  unknown: 'rgb(156, 163, 175)'
}

const chartData = computed(() => {
  if (!analyticsStore.messageTypes?.distribution) return null
  
  const distribution = analyticsStore.messageTypes.distribution
  const errorCount = analyticsStore.messageTypes.error_count
  
  // Sort by count descending
  const sorted = [...distribution].sort((a, b) => b.count - a.count)
  
  return {
    labels: sorted.map(d => d.type.charAt(0).toUpperCase() + d.type.slice(1)),
    datasets: [{
      label: 'Message Count',
      data: sorted.map(d => d.count),
      backgroundColor: sorted.map(d => messageTypeColors[d.type] || messageTypeColors.unknown),
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
      display: false
    },
    tooltip: {
      backgroundColor: isDark.value ? '#1f2937' : '#ffffff',
      titleColor: isDark.value ? '#e5e7eb' : '#111827',
      bodyColor: isDark.value ? '#d1d5db' : '#374151',
      borderColor: isDark.value ? '#374151' : '#e5e7eb',
      borderWidth: 1,
      callbacks: {
        label: function(context) {
          const value = context.parsed.y || 0
          const total = analyticsStore.messageTypes?.total || 0
          const percentage = total > 0 ? (value / total * 100).toFixed(1) : 0
          return `${value} messages (${percentage}%)`
        }
      }
    }
  },
  scales: {
    x: {
      grid: {
        display: false
      },
      ticks: {
        color: isDark.value ? '#9ca3af' : '#6b7280'
      }
    },
    y: {
      grid: {
        color: isDark.value ? '#374151' : '#e5e7eb',
        drawBorder: false
      },
      ticks: {
        color: isDark.value ? '#9ca3af' : '#6b7280',
        precision: 0
      }
    }
  }
}))
</script>