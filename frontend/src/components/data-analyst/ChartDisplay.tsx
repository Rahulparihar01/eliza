/**
 * Chart Display Component
 * Renders charts based on metadata suggestions
 */
import React from 'react';
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
} from 'recharts';
import { format, isValid, parseISO } from 'date-fns';

interface ChartDisplayProps {
  metadata: any;
  data: any;
  limit?: number; // Limit number of charts to display
}

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#0088fe', '#00c49f'];

/**
 * Format a value for chart axis display.
 * Intelligently detects dates and formats them based on granularity.
 */
const formatAxisValue = (value: any): string => {
  if (value === null || value === undefined) return '';
  
  // Try to parse as date/timestamp
  let date: Date | null = null;
  
  // Handle ISO timestamps (e.g., "2024-11-01T00:00:00+00:00")
  if (typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2}/)) {
    try {
      date = parseISO(value);
      if (!isValid(date)) date = null;
    } catch (e) {
      date = null;
    }
  }
  
  // Handle Date objects
  if (value instanceof Date && isValid(value)) {
    date = value;
  }
  
  // If it's a valid date, format based on granularity
  if (date && isValid(date)) {
    // Check if this looks like monthly data (day is 1st)
    if (date.getDate() === 1) {
      return format(date, 'MMM yyyy'); // "Nov 2024"
    }
    // Daily data
    return format(date, 'MMM dd'); // "Nov 15"
  }
  
  // Not a date - return as string
  return String(value);
};

export default function ChartDisplay({ metadata, data, limit }: ChartDisplayProps) {
  const chartSuggestions = (metadata?.chart_suggestions || []).slice(0, limit);

  if (!data || !data.rows || data.rows.length === 0) {
    return (
      <div className="bg-surface p-8 rounded-lg text-center text-muted">
        <p>No data available for visualization</p>
      </div>
    );
  }

  // Don't show charts for single data points - they add no value
  if (data.rows.length === 1) {
    return null; // Silently skip rendering - the data table will show the single value
  }

  if (chartSuggestions.length === 0) {
    return null; // Silently skip if no suggestions - don't show unnecessary message
  }

  // Transform data for charting
  const chartData = data.rows.map((row: any[]) => {
    const obj: any = {};
    data.columns.forEach((col: string, idx: number) => {
      obj[col] = row[idx];
    });
    return obj;
  });

  return (
    <div className="space-y-6">
      {chartSuggestions.map((suggestion: any, idx: number) => {
        // Support both old (type, x, y) and new (chart_type, x_axis, y_axis) field names
        const chartType = suggestion.chart_type || suggestion.type;
        const xField = suggestion.x_axis || suggestion.x;
        const yField = suggestion.y_axis || suggestion.y;
        
        // Skip if chart type is undefined
        if (!chartType) {
          console.warn('Chart suggestion missing chart_type/type field:', suggestion);
          return null;
        }
        
        return (
        <div key={idx} className="bg-surface p-6 rounded-lg border border-border">
          <h3 className="text-lg font-semibold mb-4 text-text">
            {suggestion.title || `${chartType.charAt(0).toUpperCase() + chartType.slice(1)} Chart ${idx + 1}`}
          </h3>
          <div className="h-80">
            {chartType === 'bar' && xField && yField && (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis 
                    dataKey={xField} 
                    stroke="#9ca3af"
                    tick={{ fill: '#6b7280' }}
                    tickFormatter={formatAxisValue}
                  />
                  <YAxis 
                    stroke="#9ca3af"
                    tick={{ fill: '#6b7280' }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1f2937',
                      border: '1px solid #374151',
                      borderRadius: '8px'
                    }}
                    labelFormatter={formatAxisValue}
                  />
                  <Legend />
                  {Array.isArray(yField) ? (
                    yField.map((yKey: string, yIdx: number) => (
                      <Bar 
                        key={yKey}
                        dataKey={yKey} 
                        fill={COLORS[yIdx % COLORS.length]}
                      />
                    ))
                  ) : (
                    <Bar dataKey={yField} fill={COLORS[0]} />
                  )}
                </BarChart>
              </ResponsiveContainer>
            )}
            
            {chartType === 'line' && xField && yField && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis 
                    dataKey={xField} 
                    stroke="#9ca3af"
                    tick={{ fill: '#6b7280' }}
                    tickFormatter={formatAxisValue}
                  />
                  <YAxis 
                    stroke="#9ca3af"
                    tick={{ fill: '#6b7280' }}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1f2937',
                      border: '1px solid #374151',
                      borderRadius: '8px'
                    }}
                    labelFormatter={formatAxisValue}
                  />
                  <Legend />
                  {Array.isArray(yField) ? (
                    yField.map((yKey: string, yIdx: number) => (
                      <Line 
                        key={yKey}
                        type="monotone" 
                        dataKey={yKey} 
                        stroke={COLORS[yIdx % COLORS.length]}
                        strokeWidth={2}
                      />
                    ))
                  ) : (
                    <Line type="monotone" dataKey={yField} stroke={COLORS[0]} strokeWidth={2} />
                  )}
                </LineChart>
              </ResponsiveContainer>
            )}
            
            {chartType === 'pie' && (suggestion.label || xField) && (suggestion.value || yField) && (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey={suggestion.value || yField}
                    nameKey={suggestion.label || xField}
                  >
                    {chartData.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1f2937',
                      border: '1px solid #374151',
                      borderRadius: '8px'
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
        );
      })}
    </div>
  );
}

