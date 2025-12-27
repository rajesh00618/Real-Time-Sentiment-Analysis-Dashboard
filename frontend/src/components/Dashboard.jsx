import React, { useState, useEffect } from 'react'
import DistributionChart from './DistributionChart'
import SentimentChart from './SentimentChart'
import LiveFeed from './LiveFeed'
import MetricsCards from './MetricsCards'
import { fetchDistribution, fetchAggregateData, fetchPosts, connectWebSocket } from '../services/api'

function Dashboard() {
  const [distributionData, setDistributionData] = useState({ positive: 0, negative: 0, neutral: 0 })
  const [trendData, setTrendData] = useState([])
  const [recentPosts, setRecentPosts] = useState([])
  const [metrics, setMetrics] = useState({ total: 0, positive: 0, negative: 0, neutral: 0 })
  const [connectionStatus, setConnectionStatus] = useState('connecting')
  const [lastUpdate, setLastUpdate] = useState(new Date())

  useEffect(() => {
    // Fetch initial data
    const loadInitialData = async () => {
      try {
        // Fetch distribution
        const distData = await fetchDistribution(24)
        setDistributionData(distData.distribution || { positive: 0, negative: 0, neutral: 0 })
        setMetrics({
          total: distData.total || 0,
          positive: distData.distribution?.positive || 0,
          negative: distData.distribution?.negative || 0,
          neutral: distData.distribution?.neutral || 0
        })

        // Fetch trend data (last 24 hours, hourly aggregation)
        const endDate = new Date()
        const startDate = new Date(endDate.getTime() - 24 * 60 * 60 * 1000)
        const trendResponse = await fetchAggregateData('hour', startDate, endDate)
        setTrendData(trendResponse.data || [])

        // Fetch recent posts
        const postsResponse = await fetchPosts(50, 0, {})
        setRecentPosts(postsResponse.posts || [])
      } catch (error) {
        console.error('Error loading initial data:', error)
      }
    }

    loadInitialData()

    // Establish WebSocket connection for real-time updates
    const ws = connectWebSocket(
      (message) => {
        if (message.type === 'connected') {
          setConnectionStatus('connected')
          setLastUpdate(new Date())
        } else if (message.type === 'new_post') {
          // Add new post to the feed
          setRecentPosts(prev => {
            const newPosts = [message.data, ...prev]
            return newPosts.slice(0, 50) // Keep only latest 50
          })
          setLastUpdate(new Date())
        } else if (message.type === 'metrics_update') {
          // Update metrics from WebSocket
          if (message.data && message.data.last_24_hours) {
            const newMetrics = {
              total: message.data.last_24_hours.total || 0,
              positive: message.data.last_24_hours.positive || 0,
              negative: message.data.last_24_hours.negative || 0,
              neutral: message.data.last_24_hours.neutral || 0
            }
            setMetrics(newMetrics)
            // Also update distribution data
            setDistributionData({
              positive: newMetrics.positive,
              negative: newMetrics.negative,
              neutral: newMetrics.neutral
            })
          }
          setLastUpdate(new Date())
        }
      },
      (error) => {
        console.error('WebSocket error:', error)
        setConnectionStatus('disconnected')
      },
      () => {
        setConnectionStatus('disconnected')
      }
    )

    // Cleanup WebSocket on unmount
    return () => {
      if (ws) {
        ws.close()
      }
    }
  }, [])

  const statusColor = connectionStatus === 'connected' ? 'text-green-500' : 
                      connectionStatus === 'connecting' ? 'text-yellow-500' : 'text-red-500'

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      {/* Header */}
      <div className="mb-6 flex justify-between items-center">
        <h1 className="text-3xl font-bold">Real-Time Sentiment Analysis Dashboard</h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${statusColor.replace('text-', 'bg-')}`}></span>
            <span>Status: <span className={statusColor}>{connectionStatus.charAt(0).toUpperCase() + connectionStatus.slice(1)}</span></span>
          </div>
          <div className="text-sm text-gray-400">
            Last Update: {lastUpdate.toLocaleTimeString()}
          </div>
        </div>
      </div>

      {/* Metrics Cards */}
      <MetricsCards metrics={metrics} />

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <DistributionChart data={distributionData} />
        <LiveFeed posts={recentPosts} />
      </div>

      {/* Trend Chart */}
      <div className="mb-6">
        <SentimentChart data={trendData} />
      </div>
    </div>
  )
}

export default Dashboard

