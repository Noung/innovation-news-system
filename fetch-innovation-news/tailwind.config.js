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
        primary: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd',
          400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8',
          800: '#1e40af', 900: '#1e3a8a', 950: '#172554',
        },
        secondary: {
          50: '#f5f3ff', 100: '#ede9fe', 200: '#ddd6fe', 300: '#c4b5fd',
          400: '#a78bfa', 500: '#8b5cf6', 600: '#7c3aed', 700: '#6d28d9',
          800: '#5b21b6', 900: '#4c1d95', 950: '#2e1065',
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
