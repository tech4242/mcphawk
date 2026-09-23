import { reactive } from 'vue'

// One WebSocket for the app; views watch `live.tick` to refresh.
export const live = reactive({ connected: false, tick: 0, lastBatch: [] })

let retry = 500
function connect() {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${scheme}://${window.location.host}/api/live`)
  ws.onopen = () => { live.connected = true; retry = 500 }
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'messages') {
      live.lastBatch = data.items
      live.tick++
    }
  }
  ws.onclose = () => {
    live.connected = false
    setTimeout(connect, retry)
    retry = Math.min(retry * 2, 8000)
  }
}
connect()
