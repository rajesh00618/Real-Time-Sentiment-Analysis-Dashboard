const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export async function fetchPosts(limit = 50, offset = 0, filters = {}) {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString()
  })

  if (filters.source) params.append('source', filters.source)
  if (filters.sentiment) params.append('sentiment', filters.sentiment)
  if (filters.startDate) params.append('start_date', filters.startDate.toISOString())
  if (filters.endDate) params.append('end_date', filters.endDate.toISOString())

  const response = await fetch(`${API_URL}/api/posts?${params}`)
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

export async function fetchDistribution(hours = 24) {
  const response = await fetch(`${API_URL}/api/sentiment/distribution?hours=${hours}`)
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

export async function fetchAggregateData(period, startDate, endDate, source = null) {
  const params = new URLSearchParams({
    period: period,
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString()
  })

  if (source) params.append('source', source)

  const response = await fetch(`${API_URL}/api/sentiment/aggregate?${params}`)
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

export function connectWebSocket(onMessage, onError, onClose) {
  const ws = new WebSocket(`${WS_URL}/ws/sentiment`)

  ws.onopen = () => {
    console.log('WebSocket connected')
    // Send a connected status immediately
    onMessage({ type: 'connected' })
  }

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data)
      onMessage(message)
    } catch (error) {
      console.error('Error parsing WebSocket message:', error)
    }
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
    if (onError) onError(error)
  }

  ws.onclose = () => {
    console.log('WebSocket disconnected')
    if (onClose) onClose()
  }

  return ws
}

