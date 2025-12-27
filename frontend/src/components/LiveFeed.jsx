import React from 'react'

const SENTIMENT_COLORS = {
  positive: 'bg-green-500',
  negative: 'bg-red-500',
  neutral: 'bg-gray-500'
}

const SENTIMENT_LABELS = {
  positive: 'Positive',
  negative: 'Negative',
  neutral: 'Neutral'
}

function LiveFeed({ posts }) {
  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4">Recent Posts Feed</h3>
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {posts.length === 0 ? (
          <div className="text-gray-400 text-center py-8">
            No posts yet. Posts will appear here in real-time.
          </div>
        ) : (
          posts.map((post, index) => (
            <div
              key={post.post_id || index}
              className="bg-gray-700 rounded-lg p-4 border-l-4"
              style={{
                borderLeftColor: post.sentiment_label === 'positive' ? '#10b981' :
                                 post.sentiment_label === 'negative' ? '#ef4444' : '#6b7280'
              }}
            >
              <div className="flex justify-between items-start mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">{post.source}</span>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    SENTIMENT_COLORS[post.sentiment_label] || 'bg-gray-500'
                  }`}>
                    {SENTIMENT_LABELS[post.sentiment_label] || 'Unknown'}
                  </span>
                  {post.emotion && (
                    <span className="text-xs text-gray-400">({post.emotion})</span>
                  )}
                </div>
                <span className="text-xs text-gray-500">
                  {post.timestamp ? new Date(post.timestamp).toLocaleTimeString() : ''}
                </span>
              </div>
              <p className="text-sm text-gray-200">{post.content}</p>
              {post.sentiment?.confidence !== undefined && (
                <div className="mt-2 text-xs text-gray-400">
                  Confidence: {(post.sentiment.confidence * 100).toFixed(1)}%
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default LiveFeed

