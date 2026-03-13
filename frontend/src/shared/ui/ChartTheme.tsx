import React, { createContext, useContext, useMemo } from 'react';
import { useThemeColors } from './useThemeColors';

export type ChartTheme = {
  series: string[];
  grid: string;
  text: string;
  background: string;
};

const ChartThemeContext = createContext<ChartTheme | null>(null);

export function ChartThemeProvider({ children }: { children: React.ReactNode }) {
  const { charts } = useThemeColors();
  const value = useMemo<ChartTheme>(() => ({
    series: charts.series,
    grid: charts.grid,
    text: charts.text,
    background: getComputedStyle(document.documentElement).getPropertyValue('--surface').trim(),
  }), [charts]);

  return (
    <ChartThemeContext.Provider value={value}>{children}</ChartThemeContext.Provider>
  );
}

export function useChartTheme(): ChartTheme {
  const ctx = useContext(ChartThemeContext);
  if (!ctx) {
    // Fallback based on CSS vars even without provider
    const root = getComputedStyle(document.documentElement);
    return {
      series: [
        root.getPropertyValue('--brand').trim(),
        root.getPropertyValue('--brand-strong').trim(),
        '#C96B75',
        '#8B3A52',
        '#FFB8A8',
      ],
      grid: root.getPropertyValue('--border').trim(),
      text: root.getPropertyValue('--muted').trim(),
      background: root.getPropertyValue('--surface').trim(),
    };
  }
  return ctx;
}
