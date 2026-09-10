/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#04070C',
        panel: '#0A121C',
        panel2: '#0D1724',
        ice: '#E8F1F5',
        mute: '#8FA3B0',
        dim: '#63747F',
        cyan: { DEFAULT: '#4FD8E4', deep: '#159AAE', soft: '#8DF0F8' },
        signal: '#3B76F6',
        flag: '#F2A93B',
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', 'Inter', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderColor: {
        hair: 'rgba(143,182,196,.14)',
        hairStrong: 'rgba(143,182,196,.26)',
      },
      maxWidth: { shell: '1280px' },
      transitionTimingFunction: { out: 'cubic-bezier(.2,.7,.3,1)' },
    },
  },
  plugins: [],
};
