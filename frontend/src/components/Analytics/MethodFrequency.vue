<template>
  <div class="w-full">
    <div class="mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
        Top Methods
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
        Most frequently called JSON-RPC methods
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

const loading = computed(() => analyticsStore.loading.methods)

const chartData = computed(() => {
  if (!analyticsStore.methods?.methods) return null
  
  const methods = analyticsStore.methods.methods.slice(0, 10) // Top 10
  
  return {
    labels: methods.map(m => {
      // Truncate long method names
      const name = m.method
      return name.length > 20 ? name.substring(0, 20) + '...' : name
    }),
    datasets: [{
      label: 'Call Count',
      data: methods.map(m => m.count),
      backgroundColor: 'rgb(59, 130, 246)',
      borderWidth: 0
    }]
  }
})

const isDark = computed(() => document.documentElement.classList.contains('dark'))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: 'y', // Horizontal bar chart
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
        title: function(context) {
          const index = context[0].dataIndex
          const methods = analyticsStore.methods?.methods || []
          return methods[index]?.method || ''
        },
        label: function(context) {
          return `${context.parsed.x} calls`
        }
      }
    }
  },
  scales: {
    x: {
      grid: {
        color: isDark.value ? '#374151' : '#e5e7eb',
        drawBorder: false
      },
      ticks: {
        color: isDark.value ? '#9ca3af' : '#6b7280',
        precision: 0
      }
    },
    y: {
      grid: {
        display: false
      },
      ticks: {
        color: isDark.value ? '#9ca3af' : '#6b7280'
      }
    }
  }
}))
</script>