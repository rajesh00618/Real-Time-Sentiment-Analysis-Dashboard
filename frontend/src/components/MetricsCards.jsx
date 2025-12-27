import React from 'react'

function MetricsCards({ metrics }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="text-gray-400 text-sm mb-2">Total Posts</div>
        <div className="text-3xl font-bold">{metrics.total.toLocaleString()}</div>
      </div>
      <div className="bg-gray-800 rounded-lg p-6 border-l-4 border-green-500">
        <div className="text-gray-400 text-sm mb-2">Positive</div>
        <div className="text-3xl font-bold text-green-500">{metrics.positive.toLocaleString()}</div>
        {metrics.total > 0 && (
          <div className="text-sm text-gray-400 mt-1">
            {((metrics.positive / metrics.total) * 100).toFixed(1)}%
          </div>
        )}
      </div>
      <div className="bg-gray-800 rounded-lg p-6 border-l-4 border-red-500">
        <div className="text-gray-400 text-sm mb-2">Negative</div>
        <div className="text-3xl font-bold text-red-500">{metrics.negative.toLocaleString()}</div>
        {metrics.total > 0 && (
          <div className="text-sm text-gray-400 mt-1">
            {((metrics.negative / metrics.total) * 100).toFixed(1)}%
          </div>
        )}
      </div>
      <div className="bg-gray-800 rounded-lg p-6 border-l-4 border-gray-500">
        <div className="text-gray-400 text-sm mb-2">Neutral</div>
        <div className="text-3xl font-bold text-gray-400">{metrics.neutral.toLocaleString()}</div>
        {metrics.total > 0 && (
          <div className="text-sm text-gray-400 mt-1">
            {((metrics.neutral / metrics.total) * 100).toFixed(1)}%
          </div>
        )}
      </div>
    </div>
  )
}

export default MetricsCards

