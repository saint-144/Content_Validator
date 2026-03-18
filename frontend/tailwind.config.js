/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        brand: { 50:'#eef2ff',100:'#e0e7ff',500:'#6366f1',600:'#4f46e5',700:'#4338ca',900:'#312e81' },
        surface: { DEFAULT:'#0f1117', card:'#161b27', border:'#1f2937', muted:'#374151' }
      },
      fontFamily: { sans: ['var(--font-inter)', 'system-ui', 'sans-serif'] }
    }
  },
  plugins: []
};
