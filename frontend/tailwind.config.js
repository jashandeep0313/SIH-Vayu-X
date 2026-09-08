/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Layered dark surfaces — depth comes from elevation, not borders alone
        base: '#080B12',
        surface: '#0E1420',
        raised: '#141B2A',
        overlay: '#1A2233',
        line: '#212B3C',
        'line-strong': '#2E3A4E',

        ink: '#E8EDF5',
        'ink-dim': '#8D9BB2',
        'ink-mute': '#5B6A80',

        // Brand — teal reads as ocean/atmosphere without competing with severity
        accent: '#2DD4BF',
        'accent-dim': '#14867A',

        // Reserved strictly for IMD warning levels. Never decorative.
        severity: {
          green: '#22C55E',
          yellow: '#F5B301',
          orange: '#FF7A1A',
          red: '#EF4444',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        panel: '0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6)',
      },
      animation: {
        'pulse-ring': 'pulseRing 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        shimmer: 'shimmer 1.6s ease-in-out infinite',
      },
      keyframes: {
        pulseRing: {
          '0%': { transform: 'scale(0.85)', opacity: '0.7' },
          '70%': { transform: 'scale(1.6)', opacity: '0' },
          '100%': { transform: 'scale(1.6)', opacity: '0' },
        },
        shimmer: {
          '0%, 100%': { opacity: '0.35' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
};
