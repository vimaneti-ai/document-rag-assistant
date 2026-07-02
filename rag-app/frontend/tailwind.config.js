/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        ink: {
          950: '#06080d',
          900: '#0b0f18',
          850: '#101622',
          800: '#151d2b',
          700: '#202b3c',
        },
        accent: {
          500: '#2f7cf6',
          400: '#5b9cff',
        },
      },
    },
  },
  plugins: [],
}
