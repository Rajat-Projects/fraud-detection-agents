/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0a0e1a',
          800: '#0d1224',
          700: '#111827',
          600: '#1a1f35',
          500: '#1f2937',
        },
        accent: {
          primary: '#6366f1',
          success: '#4ade80',
          warning: '#facc15',
          danger: '#f87171',
          info: '#60a5fa',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      }
    },
  },
  plugins: [],
}
