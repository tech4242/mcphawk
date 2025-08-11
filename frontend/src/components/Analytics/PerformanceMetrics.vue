<template>
  <div class="w-full">
    <div class="mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
        Performance Metrics
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
        Response time analysis and performance statistics
      </p>
    </div>
    
    <div v-if="loading" class="flex items-center justify-center" style="height: 250px;">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
    
    <div v-else-if="!performanceData" class="flex items-center justify-center" style="height: 250px;">
      <span class="text-gray-500 dark:text-gray-400">No data available</span>
    </div>
    
    <div v-else class="space-y-6">
      <!-- Percentile Stats -->
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div v-for="stat in percentileStats" :key="stat.label" class="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
          <div class="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ stat.label }}</div>
          <div class="text-xl font-semibold text-gray-900 dark:text-gray-100 mt-1">
            {{ stat.value }}
          </div>
        </div>
      </div>
      
      <!-- Response Time Distribution -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Histogram -->
        <div>
          <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Response Time Distribution</h4>
          <div class="relative" style="height: 200px;">
            <Bar v-if="histogramData" :data="histogramData" :options="histogramOptions" />
          </div>
        </div>
        
        <!-- Slowest Methods -->
        <div>
          <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Slowest Methods</h4>
          <div class="space-y-2 overflow-y-auto" style="max-height: 200px;">
            <div
              v-for="method in slowestMethods"
              :key="method.method"
              class="flex items-center justify-between bg-gray-50 dark:bg-gray-700 rounded-lg px-3 py-2"
            >
              <span class="text-sm text-gray-700 dark:text-gray-300 truncate flex-1 mr-2">
                {{ method.method }}
              </span>
              <div class="flex items-center gap-2 text-xs">
                <span class="text-gray-500 dark:text-gray-400">{{ method.count }} calls</span>
                <span class="font-medium text-gray-900 dark:text-gray-100">{{ formatTime(method.avg) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
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

const loading = computed(() => analyticsStore.loading.performance)

const performanceData = computed(() => analyticsStore.performance)

const percentileStats = computed(() => {
  const perf = performanceData.value?.response_times?.percentiles
  if (!perf) return []
  
  return [
    { label: 'Min', value: formatTime(perf.min) },
    { label: 'P50', value: formatTime(perf.p50) },
    { label: 'P90', value: formatTime(perf.p90) },
    { label: 'P95', value: formatTime(perf.p95) },
    { label: 'P99', value: formatTime(perf.p99) },
    { label: 'Max', value: formatTime(perf.max) }
  ]
})

const slowestMethods = computed(() => {
  return performanceData.value?.method_stats || []
})

const histogramData = computed(() => {
  const histogram = performanceData.value?.histogram
  if (!histogram) return null
  
  return {
    labels: histogram.map(h => h.range),
    datasets: [{
      label: 'Response Count',
      data: histogram.map(h => h.count),
      backgroundColor: 'rgb(59, 130, 246)',
      borderWidth: 0
    }]
  }
})

const isDark = computed(() => document.documentElement.classList.contains('dark'))

const histogramOptions = computed(() => ({
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
          const histogram = performanceData.value?.histogram || []
          const percentage = histogram[context.dataIndex]?.percentage || 0
          return `${value} responses (${percentage.toFixed(1)}%)`
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
        color: isDark.value ? '#9ca3af' : '#6b7280',
        maxRotation: 45,
        minRotation: 45
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

function formatTime(ms) {
  if (typeof ms !== 'number') return 'N/A'
  if (ms < 1) return '<1ms'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}
</script>