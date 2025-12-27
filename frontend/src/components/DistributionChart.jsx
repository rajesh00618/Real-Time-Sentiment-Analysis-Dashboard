import React from 'react'
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = {
  positive: '#10b981',
  negative: '#ef4444',
  neutral: '#6b7280'
}

function DistributionChart({ data }) {
  const chartData = [
    { name: 'Positive', value: data.positive || 0, color: COLORS.positive },
    { name: 'Negative', value: data.negative || 0, color: COLORS.negative },
    { name: 'Neutral', value: data.neutral || 0, color: COLORS.neutral }
  ].filter(item => item.value > 0)

  const total = (data.positive || 0) + (data.negative || 0) + (data.neutral || 0)

  const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
    if (percent === 0) return null
    const RADIAN = Math.PI / 180
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5
    const x = cx + radius * Math.cos(-midAngle * RADIAN)
    const y = cy + radius * Math.sin(-midAngle * RADIAN)

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor={x > cx ? 'start' : 'end'}
        dominantBaseline="central"
        fontSize={12}
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    )
  }

  if (total === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Sentiment Distribution</h3>
        <div className="flex items-center justify-center h-64 text-gray-400">
          No data available
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4">Sentiment Distribution</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={renderCustomLabel}
            outerRadius={100}
            fill="#8884d8"
            dataKey="value"
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value) => [
              `${value} (${((value / total) * 100).toFixed(1)}%)`,
              'Count'
            ]}
          />
          <Legend
            formatter={(value, entry) => {
              const count = entry.payload.value
              const percentage = ((count / total) * 100).toFixed(1)
              return `${value}: ${count} (${percentage}%)`
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

export default DistributionChart

