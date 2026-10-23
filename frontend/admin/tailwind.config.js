/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: '#1f2a5c', deep: '#161e44', soft: '#e8ebf5' },
        marigold: { DEFAULT: '#e7a21b', soft: '#fdf3dc' },
        ink: '#1a1e2c',
        slate2: '#5b6275',
        mist: '#eef0f6',
        line: '#dde1ec',
        leaf: '#1d7a4c',
        danger: '#b42318',
      },
      fontFamily: { sans: ['"Hind Madurai"', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
}
