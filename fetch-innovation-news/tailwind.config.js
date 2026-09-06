const path = require('path');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [path.join(__dirname, 'public/**/*.html')],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Noto Sans Thai', 'Tahoma', 'Arial', 'sans-serif'],
      },
      colors: {
        // Page canvas: very light tint of PSU Sritrang (#b6b8dc) instead of
        // pure gray — gives the whole desk a faint blue cast (user request).
        surface: {
          canvas: '#f4f5fa',
        },
        // PSU brand palette — primary remapped from Tailwind Blue to PSU Deep
        // Blue family (brand commitment). Ramp derived for WCAG AA contrast:
        // white on 600 = ~10:1, ink on 50 = high, borders on white >= 3:1.
        primary: {
          50: '#eef3f8', 100: '#b6b8dc', 200: '#9db4d0', 300: '#59cbe8',
          400: '#009cde', 500: '#315dae', 600: '#003c71', 700: '#003462',
          800: '#012b52', 900: '#012343', 950: '#011a32',
        },
        secondary: {
          50: '#f5f3ff', 100: '#ede9fe', 200: '#ddd6fe', 300: '#c4b5fd',
          400: '#a78bfa', 500: '#8b5cf6', 600: '#7c3aed', 700: '#6d28d9',
          800: '#5b21b6', 900: '#4c1d95', 950: '#2e1065',
        },
        // PSU "Summer" highlight accent (#ff8040 family) — highlight-only,
        // never actions or status (see DESIGN.md Summer Highlight Rule).
        // 600 is the readable-on-white tone (~3.9:1, large/bold text), 700 for small text (~4.9:1).
        accent: {
          50: '#fff4ec', 100: '#ffe6d5', 200: '#ffcdb0', 300: '#ffb08a',
          400: '#ff9559', 500: '#ff8040', 600: '#e86a2a', 700: '#c4541e',
          800: '#9c4218', 900: '#743113',
        },
        success: {
          50: '#f0fdf4', 100: '#dcfce7', 200: '#bbf7d0', 300: '#86efac',
          400: '#4ade80', 500: '#22c55e', 600: '#16a34a', 700: '#15803d',
          800: '#166534', 900: '#14532d',
        },
        warning: {
          50: '#fffbeb', 100: '#fef3c7', 200: '#fde68a', 300: '#fcd34d',
          400: '#fbbf24', 500: '#f59e0b', 600: '#d97706', 700: '#b45309',
          800: '#92400e', 900: '#78350f',
        },
        danger: {
          50: '#fef2f2', 100: '#fee2e2', 200: '#fecaca', 300: '#fca5a5',
          400: '#f87171', 500: '#ef4444', 600: '#dc2626', 700: '#b91c1c',
          800: '#991b1b', 900: '#7f1d1d',
        },
      },
    },
  },
  plugins: [],
  safelist: [
    // KPI card tone classes are injected at runtime via innerHTML templates
    // (renderDashboardKpis toneAccents/toneClasses), so the JIT purge cannot
    // see them in HTML. Keep the full tone matrix in the build.
    'hover:border-primary-300',
    'hover:border-success-300',
    'hover:border-warning-300',
    'hover:border-danger-300',
    'focus:ring-primary-200',
    'focus:ring-success-200',
    'focus:ring-warning-200',
    'focus:ring-danger-200',
  ],
};
