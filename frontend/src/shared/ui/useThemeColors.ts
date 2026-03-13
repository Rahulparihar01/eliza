import { useEffect, useMemo, useState } from 'react';
import { useUI } from '../../stores/useUI';

function readCssVar(name: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name);
  return v?.trim() || '';
}

export function useThemeColors() {
  const theme = useUI((s) => s.theme);
  const [vars, setVars] = useState({
    brand: '#FF9580',
    brandStrong: '#FF7B6B',
    text: '#2B1420',
    muted: '#8B3A52',
    surface: 'rgba(255,255,255,0.65)',
    surface2: 'rgba(255,255,255,0.45)',
  });

  useEffect(() => {
    setVars({
      brand: readCssVar('--brand'),
      brandStrong: readCssVar('--brand-strong'),
      text: readCssVar('--text'),
      muted: readCssVar('--muted'),
      surface: readCssVar('--surface'),
      surface2: readCssVar('--surface-2'),
    });
  }, [theme]);

  const charts = useMemo(() => ({
    series: [vars.brand, vars.brandStrong, '#C96B75', '#8B3A52', '#FFB8A8'],
    grid: readCssVar('--border'),
    text: vars.muted,
  }), [vars]);

  return { theme, vars, charts } as const;
}
