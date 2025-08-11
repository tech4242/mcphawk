<template>
  <div class="w-full">
    <div class="mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
        Error Rate Timeline
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
        Tracks error messages and error rates over time to identify issues
      </p>
    </div>
    <div v-if="loading" class="flex items-center justify-center" style="height: 300px;">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
    <div v-else-if="!chartData" class="flex items-center justify-center" style="height: 300px;">
      <span class="text-gray-500 dark:text-gray-400">No data available</span>
    </div>
    <div v-else class="relative" style="height: 300px;">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAnalyticsStore } from '@/stores/analytics'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import dayjs from 'dayjs'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const analyticsStore = useAnalyticsStore()

const loading = computed(() => analyticsStore.loading.errors)

const chartData = computed(() => {
  if (!analyticsStore.errors?.data) return null
  
  const data = analyticsStore.errors.data
  const labels = data.map(d => dayjs(d.timestamp).format('HH:mm'))
  
  return {
    labels,
    datasets: [
      {
        label: 'Error Rate (%)',
        data: data.map(d => d.error_rate),
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        tension: 0.3,
        fill: true,
        yAxisID: 'y'
      },
      {
        label: 'Error Count',
        data: data.map(d => d.errors),
        borderColor: 'rgb(252, 165, 165)',
        backgroundColor: 'rgba(252, 165, 165, 0.1)',
        tension: 0.3,
        fill: false,
        yAxisID: 'y1',
        borderDash: [5, 5]
      }
    ]
  }
})

const isDark = computed(() => document.documentElement.classList.contains('dark'))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index',
    intersect: false
  },
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        color: isDark.value ? '#e5e7eb' : '#374151',
        usePointStyle: true,
        padding: 15
      }
    },
    tooltip: {
      mode: 'index',
      intersect: false,
      backgroundColor: isDark.value ? '#1f2937' : '#ffffff',
      titleColor: isDark.value ? '#e5e7eb' : '#111827',
      bodyColor: isDark.value ? '#d1d5db' : '#374151',
      borderColor: isDark.value ? '#374151' : '#e5e7eb',
      borderWidth: 1,
      callbacks: {
        label: function(context) {
          let label = context.dataset.label || ''
          if (context.parsed.y !== null) {
            if (label.includes('Rate')) {
              label += ': ' + context.parsed.y.toFixed(2) + '%'
            } else {
              label += ': ' + context.parsed.y
            }
          }
          // Add total messages for context
          if (context.datasetIndex === 0) {
            const dataPoint = analyticsStore.errors?.data[context.dataIndex]
            if (dataPoint) {
              label += ` (${dataPoint.errors}/${dataPoint.total} messages)`
            }
          }
          return label
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
        color: isDark.value ? '#9ca3af' : '#6b7280'
      }
    },
    y: {
      type: 'linear',
      display: true,
      position: 'left',
      title: {
        display: true,
        text: 'Error Rate (%)',
        color: isDark.value ? '#9ca3af' : '#6b7280'
      },
      grid: {
        color: isDark.value ? '#374151' : '#e5e7eb',
        drawBorder: false
      },
      ticks: {
        color: isDark.value ? '#9ca3af' : '#6b7280',
        callback: function(value) {
          return value + '%'
        }
      }
    },
    y1: {
      type: 'linear',
      display: true,
      position: 'right',
      title: {
        display: true,
        text: 'Error Count',
        color: isDark.value ? '#9ca3af' : '#6b7280'
      },
      grid: {
        drawOnChartArea: false
      },
      ticks: {
        color: isDark.value ? '#9ca3af' : '#6b7280',
        precision: 0
      }
    }
  }
}))
</script>