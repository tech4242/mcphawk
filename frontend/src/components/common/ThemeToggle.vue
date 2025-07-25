<template>
  <button
    @click="toggleTheme"
    class="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
    :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
  >
    <SunIcon v-if="isDark" class="h-5 w-5" />
    <MoonIcon v-else class="h-5 w-5" />
  </button>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { SunIcon, MoonIcon } from '@heroicons/vue/24/outline'

const isDark = ref(false)
let mediaQuery = null

onMounted(() => {
  // Check for saved theme preference or system preference
  const savedTheme = localStorage.getItem('theme')
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  
  // Use saved theme if available, otherwise use system preference
  if (savedTheme) {
    isDark.value = savedTheme === 'dark'
  } else {
    isDark.value = mediaQuery.matches
  }
  
  applyTheme()
  
  // Listen for system theme changes (only if user hasn't set a preference)
  const handleSystemThemeChange = (e) => {
    if (!localStorage.getItem('theme')) {
      isDark.value = e.matches
      applyTheme()
    }
  }
  
  mediaQuery.addEventListener('change', handleSystemThemeChange)
  
  // Cleanup on unmount
  onUnmounted(() => {
    mediaQuery.removeEventListener('change', handleSystemThemeChange)
  })
})

function toggleTheme() {
  isDark.value = !isDark.value
  applyTheme()
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

function applyTheme() {
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}
</script>