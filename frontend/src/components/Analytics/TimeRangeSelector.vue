<template>
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-4">
    <div class="flex flex-wrap items-center gap-4">
      <!-- Quick Range Buttons -->
      <div class="flex gap-2">
        <button
          v-for="range in quickRanges"
          :key="range.label"
          @click="selectQuickRange(range)"
          :class="[
            'px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200',
            selectedRange === range.label
              ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
              : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700'
          ]"
        >
          {{ range.label }}
        </button>
      </div>

      <!-- Custom Date Range Picker -->
      <div class="flex items-center gap-2">
        <span class="text-sm text-gray-500 dark:text-gray-400">Custom:</span>
        <VueDatePicker
          v-model="dateRange"
          range
          :enable-time-picker="false"
          :dark="isDark"
          :format="dateFormat"
          :preview-format="dateFormat"
          placeholder="Select date range"
          @update:model-value="onDateRangeChange"
          class="w-72"
        />
      </div>

      <!-- Interval Selector -->
      <div class="flex items-center gap-2 ml-auto">
        <span class="text-sm text-gray-500 dark:text-gray-400">Interval:</span>
        <select
          v-model="intervalMinutes"
          @change="onIntervalChange"
          class="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option :value="1">1 min</option>
          <option :value="5">5 min</option>
          <option :value="10">10 min</option>
          <option :value="15">15 min</option>
          <option :value="30">30 min</option>
          <option :value="60">1 hour</option>
        </select>
      </div>

      <!-- Refresh Button -->
      <button
        @click="refresh"
        :disabled="loading"
        class="p-2 rounded-lg text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200 disabled:opacity-50"
        title="Refresh data"
      >
        <ArrowPathIcon :class="['h-5 w-5', loading && 'animate-spin']" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAnalyticsStore } from '@/stores/analytics'
import VueDatePicker from '@vuepic/vue-datepicker'
import '@vuepic/vue-datepicker/dist/main.css'
import { ArrowPathIcon } from '@heroicons/vue/24/outline'
import dayjs from 'dayjs'

const analyticsStore = useAnalyticsStore()

const dateRange = ref([])
const selectedRange = ref('Last Hour')
const intervalMinutes = ref(5)

const isDark = computed(() => {
  return document.documentElement.classList.contains('dark')
})

const loading = computed(() => {
  return Object.values(analyticsStore.loading).some(v => v)
})

const quickRanges = [
  { label: 'All Data', special: 'all' },
  { label: 'Last Hour', hours: 1 },
  { label: 'Last 6 Hours', hours: 6 },
  { label: 'Last 24 Hours', hours: 24 },
  { label: 'Last 7 Days', days: 7 },
  { label: 'Last 30 Days', days: 30 }
]

const dateFormat = (dates) => {
  if (!dates) return ''
  if (Array.isArray(dates)) {
    const start = dayjs(dates[0]).format('MMM D, YYYY')
    const end = dates[1] ? dayjs(dates[1]).format('MMM D, YYYY') : ''
    return end ? `${start} - ${end}` : start
  }
  return dayjs(dates).format('MMM D, YYYY')
}

function selectQuickRange(range) {
  selectedRange.value = range.label
  
  // Handle "All Data" special case - don't set dates, let backend use full range
  if (range.special === 'all') {
    dateRange.value = []
    analyticsStore.setTimeRange(null, null)
    return
  }
  
  // For other ranges, just use current time
  // The backend will handle it if there's no data in that range
  const now = new Date()
  let start
  
  if (range.hours) {
    start = new Date(now.getTime() - range.hours * 60 * 60 * 1000)
  } else if (range.days) {
    start = new Date(now.getTime() - range.days * 24 * 60 * 60 * 1000)
  }
  
  dateRange.value = [start, now]
  updateTimeRange()
}

function onDateRangeChange() {
  selectedRange.value = null // Clear quick range selection
  updateTimeRange()
}

function updateTimeRange() {
  if (dateRange.value && dateRange.value.length === 2) {
    const [start, end] = dateRange.value
    
    // Auto-adjust interval based on date range
    const rangeDays = dayjs(end).diff(dayjs(start), 'day')
    if (rangeDays > 30) {
      intervalMinutes.value = 60 * 24 // Daily for > 1 month
    } else if (rangeDays > 7) {
      intervalMinutes.value = 60 * 6 // 6 hours for > 1 week
    } else if (rangeDays > 2) {
      intervalMinutes.value = 60 // Hourly for > 2 days
    } else if (rangeDays > 0) {
      intervalMinutes.value = 15 // 15 min for 1-2 days
    } else {
      intervalMinutes.value = 5 // 5 min for same day
    }
    
    analyticsStore.setIntervalMinutes(intervalMinutes.value)
    analyticsStore.setTimeRange(
      start.toISOString(),
      end.toISOString()
    )
  }
}

function onIntervalChange() {
  analyticsStore.setIntervalMinutes(intervalMinutes.value)
}

function refresh() {
  analyticsStore.fetchAllMetrics()
}

onMounted(() => {
  // Force test with specific August date range
  dateRange.value = [new Date('2025-08-02'), new Date('2025-08-08')]
  updateTimeRange()
  intervalMinutes.value = analyticsStore.timeRange.intervalMinutes
  selectedRange.value = 'Custom Range'
})
</script>

<style>
/* Custom styles for the date picker in dark mode */
.dp__theme_dark {
  --dp-background-color: rgb(31 41 55);
  --dp-text-color: rgb(209 213 219);
  --dp-hover-color: rgb(55 65 81);
  --dp-hover-text-color: #ffffff;
  --dp-hover-icon-color: #959595;
  --dp-primary-color: rgb(59 130 246);
  --dp-primary-text-color: #ffffff;
  --dp-secondary-color: rgb(107 114 128);
  --dp-border-color: rgb(75 85 99);
  --dp-menu-border-color: rgb(75 85 99);
  --dp-border-color-hover: rgb(107 114 128);
}
</style>