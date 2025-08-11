<template>
  <div class="w-full">
    <div class="mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
        Request/Response Timeline
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
        Shows the volume of MCP messages over time, broken down by type (requests, responses, notifications, and errors)
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

const loading = computed(() => analyticsStore.loading.timeseries)

const chartData = computed(() => {
  if (!analyticsStore.timeseries?.data) return null
  
  const data = analyticsStore.timeseries.data
  
  // Format labels based on data range
  const startTime = dayjs(analyticsStore.timeseries.start_time)
  const endTime = dayjs(analyticsStore.timeseries.end_time)
  const rangeDays = endTime.diff(startTime, 'day')
  
  let labelFormat = 'HH:mm' // Default for single day
  if (rangeDays > 7) {
    labelFormat = 'MMM D' // Just date for long ranges
  } else if (rangeDays > 1) {
    labelFormat = 'MMM D HH:mm' // Date and time for multi-day
  }
  
  const labels = data.map(d => dayjs(d.timestamp).format(labelFormat))
  
  return {
    labels,
    datasets: [
      {
        label: 'Requests',
        data: data.map(d => d.requests),
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: 'Responses',
        data: data.map(d => d.responses),
        borderColor: 'rgb(34, 197, 94)',
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: 'Notifications',
        data: data.map(d => d.notifications),
        borderColor: 'rgb(168, 85, 247)',
        backgroundColor: 'rgba(168, 85, 247, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: 'Errors',
        data: data.map(d => d.errors),
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        tension: 0.3,
        fill: true
      }
    ]
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
      borderWidth: 1
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
        maxRotation: 45,
        minRotation: 0,
        autoSkip: true,
        maxTicksLimit: 15 // Limit number of labels shown
      }
    },
    y: {
      title: {
        display: true,
        text: 'Number of Messages',
        color: isDark.value ? '#9ca3af' : '#6b7280',
        font: {
          size: 12
        }
      },
      grid: {
        color: isDark.value ? '#374151' : '#e5e7eb',
        drawBorder: false
      },
      ticks: {
        color: isDark.value ? '#9ca3af' : '#6b7280',
        precision: 0
      }
    }
  },
  interaction: {
    mode: 'nearest',
    axis: 'x',
    intersect: false
  }
}))
</script>