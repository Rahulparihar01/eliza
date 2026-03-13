/**
 * ChartCanvasViewer - Chart Display for CanvasPanel
 * 
 * A chart viewer component designed to render inside the CanvasPanel.
 * Supports bar, line, and pie charts using Recharts with DS theming.
 * 
 * Part of the Eliza Forge Design System.
 */

import * as React from "react"
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { format, isValid, parseISO } from 'date-fns'
import { cn } from "../../shared/lib/cn"
import { ChartBarIcon, ArrowsPointingOutIcon } from "@heroicons/react/24/outline"

/* ============================================
   TYPES
   ============================================ */

export type ChartType = "bar" | "line" | "pie"

export interface ChartSuggestion {
  chart_type?: ChartType
  type?: ChartType  // Legacy field name
  x_axis?: string
  x?: string  // Legacy field name
  y_axis?: string | string[]
  y?: string | string[]  // Legacy field name
  label?: string
  value?: string
  title?: string
}

export interface ChartData {
  columns: string[]
  rows: any[][]
  row_count?: number
}

export interface ChartCanvasViewerProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Chart suggestion with type, axes, etc. */
  suggestion: ChartSuggestion
  /** Raw data with columns and rows */
  data: ChartData
  /** Chart title override */
  title?: string
  /** Show fullscreen button in header */
  showFullscreenButton?: boolean
}

/* ============================================
   CONSTANTS
   ============================================ */

// DS-aligned color palette - charcoal primary with accent colors
const CHART_COLORS = [
  '#1a1a1a',  // Charcoal (primary)
  '#6b7280',  // Gray-500
  '#9ca3af',  // Gray-400
  '#d1d5db',  // Gray-300
  '#374151',  // Gray-700
  '#4b5563',  // Gray-600
]

// Alternative vibrant palette for multi-series
const VIBRANT_COLORS = [
  '#2563eb',  // Blue-600
  '#16a34a',  // Green-600
  '#ea580c',  // Orange-600
  '#9333ea',  // Purple-600
  '#0891b2',  // Cyan-600
  '#db2777',  // Pink-600
]

/* ============================================
   HELPERS
   ============================================ */

/**
 * Format a value for chart axis display.
 * Intelligently detects dates and formats them based on granularity.
 */
const formatAxisValue = (value: any): string => {
  if (value === null || value === undefined) return ''
  
  // Try to parse as date/timestamp
  let date: Date | null = null
  
  // Handle ISO timestamps (e.g., "2024-11-01T00:00:00+00:00")
  if (typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2}/)) {
    try {
      date = parseISO(value)
      if (!isValid(date)) date = null
    } catch {
      date = null
    }
  }
  
  // Handle Date objects
  if (value instanceof Date && isValid(value)) {
    date = value
  }
  
  // If it's a valid date, format based on granularity
  if (date && isValid(date)) {
    // Check if this looks like monthly data (day is 1st)
    if (date.getDate() === 1) {
      return format(date, 'MMM yyyy') // "Nov 2024"
    }
    // Daily data
    return format(date, 'MMM dd') // "Nov 15"
  }
  
  // Not a date - return as string
  return String(value)
}

/**
 * Format numbers for display
 */
const formatNumber = (value: any): string => {
  if (typeof value === 'number') {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M`
    }
    if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}K`
    }
    return value.toLocaleString()
  }
  return String(value)
}

/* ============================================
   CHART CANVAS VIEWER
   ============================================ */

const ChartCanvasViewer = React.forwardRef<HTMLDivElement, ChartCanvasViewerProps>(
  (
    {
      className,
      suggestion,
      data,
      title,
      showFullscreenButton = false,
      ...props
    },
    ref
  ) => {
    // Normalize field names (support both old and new)
    const chartType = suggestion.chart_type || suggestion.type || 'bar'
    const xField = suggestion.x_axis || suggestion.x
    const yField = suggestion.y_axis || suggestion.y
    const labelField = suggestion.label || xField
    const valueField = suggestion.value || yField

    // Transform data for charting
    const chartData = React.useMemo(() => {
      if (!data?.rows || !data?.columns) return []
      
      return data.rows.map((row: any[]) => {
        const obj: Record<string, any> = {}
        data.columns.forEach((col: string, idx: number) => {
          obj[col] = row[idx]
        })
        return obj
      })
    }, [data])

    // Determine chart title
    const chartTitle = title || suggestion.title || 
      `${chartType.charAt(0).toUpperCase() + chartType.slice(1)} Chart`

    // Use vibrant colors for multi-series, charcoal for single series
    const colors = Array.isArray(yField) && yField.length > 1 ? VIBRANT_COLORS : CHART_COLORS

    // Check if we have valid data
    if (!chartData.length || chartData.length < 2) {
      return (
        <div
          ref={ref}
          className={cn(
            "flex flex-col items-center justify-center h-full p-8",
            "bg-white dark:bg-dark-surface",
            "text-gray-500 dark:text-gray-400",
            className
          )}
          {...props}
        >
          <ChartBarIcon className="w-12 h-12 mb-4 opacity-50" />
          <p className="text-sm">Not enough data to visualize</p>
          <p className="text-xs mt-1">Charts require at least 2 data points</p>
        </div>
      )
    }

    // Custom tooltip styles
    const tooltipStyle = {
      backgroundColor: 'var(--color-dark-surface, #1f2937)',
      border: '1px solid var(--color-dark-border, #374151)',
      borderRadius: '8px',
      color: '#fff',
      padding: '8px 12px',
    }

    return (
      <div
        ref={ref}
        className={cn(
          "flex flex-col h-full w-full overflow-hidden",
          "bg-white dark:bg-dark-surface",
          className
        )}
        {...props}
      >
        {/* Header */}
        <div className={cn(
          "flex items-center justify-between px-4 py-3 shrink-0 border-b",
          "bg-gray-50 dark:bg-dark-surface-2",
          "border-gray-200 dark:border-dark-border/50"
        )}>
          <div className="flex items-center gap-2">
            <ChartBarIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <h3 className="text-sm font-semibold text-charcoal dark:text-gray-100">
              {chartTitle}
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {chartData.length} data points
            </span>
          </div>
        </div>

        {/* Chart Content */}
        <div className="flex-1 p-4 min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            {chartType === 'bar' && xField && yField ? (
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                <CartesianGrid 
                  strokeDasharray="3 3" 
                  stroke="var(--color-gray-200, #e5e7eb)"
                  className="dark:opacity-20"
                />
                <XAxis 
                  dataKey={xField as string}
                  stroke="var(--color-gray-400, #9ca3af)"
                  tick={{ fill: 'var(--color-gray-500, #6b7280)', fontSize: 11 }}
                  tickFormatter={formatAxisValue}
                  angle={-45}
                  textAnchor="end"
                  height={60}
                />
                <YAxis 
                  stroke="var(--color-gray-400, #9ca3af)"
                  tick={{ fill: 'var(--color-gray-500, #6b7280)', fontSize: 11 }}
                  tickFormatter={formatNumber}
                />
                <Tooltip 
                  contentStyle={tooltipStyle}
                  labelFormatter={formatAxisValue}
                  formatter={(value: any) => [formatNumber(value), '']}
                />
                <Legend 
                  wrapperStyle={{ paddingTop: '20px' }}
                />
                {Array.isArray(yField) ? (
                  yField.map((yKey: string, yIdx: number) => (
                    <Bar 
                      key={yKey}
                      dataKey={yKey} 
                      fill={colors[yIdx % colors.length]}
                      radius={[4, 4, 0, 0]}
                    />
                  ))
                ) : (
                  <Bar 
                    dataKey={yField as string} 
                    fill={colors[0]}
                    radius={[4, 4, 0, 0]}
                  />
                )}
              </BarChart>
            ) : chartType === 'line' && xField && yField ? (
              <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                <CartesianGrid 
                  strokeDasharray="3 3" 
                  stroke="var(--color-gray-200, #e5e7eb)"
                  className="dark:opacity-20"
                />
                <XAxis 
                  dataKey={xField as string}
                  stroke="var(--color-gray-400, #9ca3af)"
                  tick={{ fill: 'var(--color-gray-500, #6b7280)', fontSize: 11 }}
                  tickFormatter={formatAxisValue}
                  angle={-45}
                  textAnchor="end"
                  height={60}
                />
                <YAxis 
                  stroke="var(--color-gray-400, #9ca3af)"
                  tick={{ fill: 'var(--color-gray-500, #6b7280)', fontSize: 11 }}
                  tickFormatter={formatNumber}
                />
                <Tooltip 
                  contentStyle={tooltipStyle}
                  labelFormatter={formatAxisValue}
                  formatter={(value: any) => [formatNumber(value), '']}
                />
                <Legend 
                  wrapperStyle={{ paddingTop: '20px' }}
                />
                {Array.isArray(yField) ? (
                  yField.map((yKey: string, yIdx: number) => (
                    <Line 
                      key={yKey}
                      type="monotone" 
                      dataKey={yKey} 
                      stroke={colors[yIdx % colors.length]}
                      strokeWidth={2}
                      dot={{ fill: colors[yIdx % colors.length], strokeWidth: 0, r: 4 }}
                      activeDot={{ r: 6, strokeWidth: 0 }}
                    />
                  ))
                ) : (
                  <Line 
                    type="monotone" 
                    dataKey={yField as string} 
                    stroke={colors[0]}
                    strokeWidth={2}
                    dot={{ fill: colors[0], strokeWidth: 0, r: 4 }}
                    activeDot={{ r: 6, strokeWidth: 0 }}
                  />
                )}
              </LineChart>
            ) : chartType === 'pie' && labelField && valueField ? (
              <PieChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  labelLine={true}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius="70%"
                  fill={colors[0]}
                  dataKey={valueField as string}
                  nameKey={labelField as string}
                  stroke="var(--color-white, #fff)"
                  strokeWidth={2}
                >
                  {chartData.map((_, index: number) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={VIBRANT_COLORS[index % VIBRANT_COLORS.length]} 
                    />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={tooltipStyle}
                  formatter={(value: any) => [formatNumber(value), '']}
                />
                <Legend />
              </PieChart>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                <p>Unable to render chart: missing axis configuration</p>
              </div>
            )}
          </ResponsiveContainer>
        </div>

        {/* Footer */}
        <div className={cn(
          "flex items-center justify-between px-4 py-2 shrink-0 border-t",
          "bg-gray-50 dark:bg-dark-surface-2",
          "border-gray-200 dark:border-dark-border/50"
        )}>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {chartType.charAt(0).toUpperCase() + chartType.slice(1)} chart • {xField} vs {Array.isArray(yField) ? yField.join(', ') : yField}
          </p>
        </div>
      </div>
    )
  }
)
ChartCanvasViewer.displayName = "ChartCanvasViewer"

/* ============================================
   CHART THUMBNAIL (for inline display)
   ============================================ */

export interface ChartThumbnailProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Chart type icon */
  chartType: ChartType
  /** Title */
  title: string
  /** Data point count */
  dataPoints?: number
}

const ChartThumbnail = React.forwardRef<HTMLButtonElement, ChartThumbnailProps>(
  ({ className, chartType, title, dataPoints, onClick, ...props }, ref) => {
    return (
      <button
        ref={ref}
        type="button"
        onClick={onClick}
        className={cn(
          "flex items-center gap-3 p-3 rounded-lg w-full text-left",
          "border border-gray-200 dark:border-dark-border/50",
          "bg-white dark:bg-dark-surface",
          "hover:border-gray-400 dark:hover:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-surface-2",
          "transition-colors duration-150",
          "group",
          className
        )}
        {...props}
      >
        <div className={cn(
          "flex items-center justify-center w-10 h-10 rounded-lg",
          "bg-gray-100 dark:bg-dark-surface-2",
          "group-hover:bg-gray-200 dark:group-hover:bg-dark-surface-3",
          "transition-colors duration-150"
        )}>
          <ChartBarIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-charcoal dark:text-white truncate">
            {title}
          </p>
          {dataPoints && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {dataPoints} data points
            </p>
          )}
        </div>
        <ArrowsPointingOutIcon className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
      </button>
    )
  }
)
ChartThumbnail.displayName = "ChartThumbnail"

export { ChartCanvasViewer, ChartThumbnail }
