/** @type {import('tailwindcss').Config} */

// Palette from the Prosperon design system: navy #1C2738, sage #7FAF9A, gold #D3AF37.
// Ramp percentages follow the source file (10% = lightest tint, 100% = darkest shade).
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          10: '#D2D4D8',
          20: '#B3B7BE',
          30: '#8E939D',
          40: '#686F7C',
          50: '#424B5C',
          DEFAULT: '#1C2738',
          60: '#172131',
          70: '#131A27',
          80: '#0E141E',
          90: '#090D14',
          100: '#06080C',
        },
        sage: {
          10: '#E5EFEB',
          20: '#D4E4DD',
          30: '#BFD7CD',
          40: '#AACABC',
          50: '#94BCAB',
          DEFAULT: '#7FAF9A',
          60: '#6A9280',
          70: '#557567',
          80: '#40584D',
          90: '#2A3A33',
          100: '#19231F',
        },
        gold: {
          10: '#F6EFD7',
          20: '#F0E4BC',
          30: '#E9D79B',
          40: '#E2CA7A',
          50: '#DABC58',
          DEFAULT: '#D3AF37',
          60: '#B0922E',
          70: '#8D7525',
          80: '#6A581C',
          90: '#463A12',
          100: '#2A230B',
        },

        // Semantic surfaces — depth from elevation, not heavy outlines
        canvas: '#090D14',
        surface: '#0E141E',
        raised: '#131A27',
        overlay: '#172131',
        hairline: '#1C2738',
        'hairline-strong': '#2B3648',

        ink: '#D2D4D8',
        'ink-dim': '#8E939D',
        'ink-mute': '#686F7C',

        // IMD warning levels — tuned into the palette but kept unmistakable
        severity: {
          green: '#7FAF9A',
          yellow: '#D3AF37',
          orange: '#E07A3F',
          red: '#D4544E',
        },
      },
      fontFamily: {
        sans: ['Urbanist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"DM Sans"', 'Urbanist', 'ui-sans-serif', 'sans-serif'],
        mono: ['"Courier New"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      letterSpacing: {
        label: '0.10em',
      },
      boxShadow: {
        panel: '0 1px 0 rgba(255,255,255,.02) inset, 0 12px 32px -20px rgba(0,0,0,.9)',
        lift: '0 18px 40px -24px rgba(0,0,0,.95)',
      },
      keyframes: {
        pulseRing: {
          '0%': { transform: 'scale(0.85)', opacity: '0.6' },
          '70%,100%': { transform: 'scale(1.7)', opacity: '0' },
        },
        shimmer: {
          '0%,100%': { opacity: '0.3' },
          '50%': { opacity: '0.6' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
