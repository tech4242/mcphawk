import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useLogStore } from './logs'

export const useWebSocketStore = defineStore('websocket', () => {
  // State
  const ws = ref(null)
  const connected = ref(false)
  const reconnectTimeout = ref(null)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 10
  const reconnectDelay = 3000

  // Actions
  function connect() {
    if (ws.value?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws`
    
    console.log('Connecting to WebSocket:', wsUrl)
    
    ws.value = new WebSocket(wsUrl)
    
    ws.value.onopen = () => {
      console.log('WebSocket connected')
      connected.value = true
      reconnectAttempts.value = 0
      clearTimeout(reconnectTimeout.value)
    }
    
    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        // Handle ping/pong
        if (data.type === 'ping') {
          if (ws.value?.readyState === WebSocket.OPEN) {
            ws.value.send(JSON.stringify({ type: 'pong' }))
          }
          return
        }
        
        // Add log to store
        const logStore = useLogStore()
        logStore.addLog(data)
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err)
      }
    }
    
    ws.value.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
    
    ws.value.onclose = () => {
      console.log('WebSocket disconnected')
      connected.value = false
      ws.value = null
      
      // Attempt to reconnect
      if (reconnectAttempts.value < maxReconnectAttempts) {
        reconnectAttempts.value++
        console.log(`Reconnecting in ${reconnectDelay}ms... (attempt ${reconnectAttempts.value})`)
        
        reconnectTimeout.value = setTimeout(() => {
          connect()
        }, reconnectDelay)
      }
    }
  }

  function disconnect() {
    clearTimeout(reconnectTimeout.value)
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connected.value = false
  }

  function send(data) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(data))
    }
  }

  return {
    // State
    connected,
    reconnectAttempts,
    
    // Actions
    connect,
    disconnect,
    send
  }
})