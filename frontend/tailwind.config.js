/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      colors: {
        // ==========================================
        // Eliza Forge Brand Colors (CSS Variable Based)
        // These reference CSS variables for runtime theming
        // ==========================================
        
        // Brand Colors (themeable via CSS variables)
        'eliza-red': {
          DEFAULT: 'rgb(var(--color-primary) / <alpha-value>)',
          light: 'rgb(var(--color-primary-light) / <alpha-value>)',
          coral: 'rgb(var(--color-accent) / <alpha-value>)',
        },
        
        // Text Colors
        charcoal: 'rgb(var(--color-text) / <alpha-value>)',
        
        // Canvas & Surfaces (Light mode)
        canvas: '#F9FAFB',
        
        // Dark mode surfaces (Cool blue-tinted - Linear/Vercel style)
        'dark-bg': 'rgb(var(--color-dark-bg) / <alpha-value>)',
        'dark-surface': 'rgb(var(--color-dark-surface) / <alpha-value>)',
        'dark-surface-2': 'rgb(var(--color-dark-surface-2) / <alpha-value>)',
        'dark-border': 'rgb(var(--color-dark-border) / <alpha-value>)',
        
        // ==========================================
        // Legacy colors (keeping for compatibility)
        // ==========================================
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        'surface-2': 'var(--surface-2)',
        text: 'var(--text)',
        muted: 'var(--muted)',
        'muted-2': 'var(--muted-2)',
        border: 'var(--border)',
        'border-strong': 'var(--border-strong)',
        brand: 'var(--brand)',
        'brand-strong': 'var(--brand-strong)',
        'brand-soft': 'var(--brand-soft)',
        'on-brand': 'var(--on-brand)',
        
        // AI Platform specific colors
        'ai-success': 'var(--ai-success)',
        'ai-warning': 'var(--ai-warning)',
        'ai-danger': 'var(--ai-danger)',
        'ai-info': 'var(--ai-info)',
        'ai-purple': 'var(--ai-purple)',
        'ai-teal': 'var(--ai-teal)',
        
        // Department colors
        'dept-sales': 'var(--dept-sales)',
        'dept-marketing': 'var(--dept-marketing)',
        'dept-engineering': 'var(--dept-engineering)',
        'dept-hr': 'var(--dept-hr)',
        'dept-finance': 'var(--dept-finance)',
        'dept-operations': 'var(--dept-operations)',
        
        // ROI status colors
        'roi-high': 'var(--roi-high)',
        'roi-medium': 'var(--roi-medium)',
        'roi-low': 'var(--roi-low)',
        'roi-unknown': 'var(--roi-unknown)',
        
        // Progress states
        'progress-not-started': 'var(--progress-not-started)',
        'progress-in-progress': 'var(--progress-in-progress)',
        'progress-completed': 'var(--progress-completed)',
        'progress-blocked': 'var(--progress-blocked)',
      },
      fontFamily: {
        // Normal text
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        // Title font
        title: ['Libre Baskerville', 'Georgia', 'serif'],
        // Subtitle font
        subtitle: ['Hedvig Letters Serif', 'Georgia', 'serif'],
        // Code
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        'display': '3.0rem',
        'h1': '1.875rem',
        'h2': '1.5rem',
        'h3': '1.25rem',
        'body': '1.0rem',
        'small': '0.875rem',
        'micro': '0.75rem',
        'metric': '2.25rem',
        'data': '0.875rem',
        'code': '0.8125rem',
      },
      spacing: {
        '1': 'var(--space-1)',
        '2': 'var(--space-2)',
        '3': 'var(--space-3)',
        '4': 'var(--space-4)',
        '5': 'var(--space-5)',
        '6': 'var(--space-6)',
        '8': 'var(--space-8)',
        '12': 'var(--space-12)',
        '16': 'var(--space-16)',
      },
      borderRadius: {
        'sm': 'var(--radius-sm)',
        'md': 'var(--radius-md)',
        'lg': 'var(--radius-lg)',
        'full': 'var(--radius-full)',
      },
      boxShadow: {
        '1': 'var(--shadow-1)',
        '2': 'var(--shadow-2)',
        // Editorial OS shadows
        'card': '0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025)',
        'card-hover': '0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 10px 10px -5px rgba(0, 0, 0, 0.03)',
      },
      transitionDuration: {
        'fast': '150ms',
        'normal': '200ms',
        'slow': '250ms',
      },
      transitionTimingFunction: {
        'brand': 'cubic-bezier(0.2, 0, 0, 1)',
      },
      animation: {
        'shimmer': 'shimmer 1.2s linear infinite',
        // Sheet/Modal animations
        'slide-in-from-right': 'slide-in-from-right 0.3s ease-out',
        'slide-in-from-left': 'slide-in-from-left 0.3s ease-out',
        'slide-in-from-top': 'slide-in-from-top 0.3s ease-out',
        'slide-in-from-bottom': 'slide-in-from-bottom 0.3s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
      },
      keyframes: {
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        'slide-in-from-right': {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        'slide-in-from-left': {
          '0%': { transform: 'translateX(-100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        'slide-in-from-top': {
          '0%': { transform: 'translateY(-100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'slide-in-from-bottom': {
          '0%': { transform: 'translateY(100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
