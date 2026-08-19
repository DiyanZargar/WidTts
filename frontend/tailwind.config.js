/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        void: "#040d0a",
        darkGraphite: "#09090B",
        accent: {
          dim: "hsl(165, 85%, 22%)",
          mid: "hsl(160, 90%, 42%)",
          bright: "hsl(155, 95%, 58%)",
          bloom: "hsl(150, 100%, 82%)",
        },
        ink: {
          100: "rgba(255, 255, 255, 1)",
          60: "rgba(255, 255, 255, 0.72)",
          35: "rgba(255, 255, 255, 0.42)",
        },
        warn: "hsl(28, 85%, 58%)",
      },
      fontFamily: {
        display: ["Outfit", "Plus Jakarta Sans", "sans-serif"],
        body: ["Plus Jakarta Sans", "Inter", "sans-serif"],
      },
      animation: {
        'orbit': 'orbit 20s linear infinite',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        orbit: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        }
      }
    },
  },
  plugins: [],
}

