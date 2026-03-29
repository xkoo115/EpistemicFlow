/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class', // 强制使用 class 策略的暗黑模式
  theme: {
    extend: {
      colors: {
        // EpistemicFlow 专属状态高亮色系
        'accent-cyan': {
          DEFAULT: '#00D9FF',
          50: '#E6FAFF',
          100: '#B3F0FF',
          200: '#80E6FF',
          300: '#4DDCFF',
          400: '#1AD2FF',
          500: '#00D9FF',
          600: '#00AACC',
          700: '#007A99',
          800: '#004966',
          900: '#001933',
        },
        'accent-amber': {
          DEFAULT: '#FFB800',
          50: '#FFF8E6',
          100: '#FFEDB3',
          200: '#FFE280',
          300: '#FFD74D',
          400: '#FFCC1A',
          500: '#FFB800',
          600: '#CC9300',
          700: '#996E00',
          800: '#664A00',
          900: '#332500',
        },
        'accent-red': {
          DEFAULT: '#FF3B3B',
          50: '#FFE8E8',
          100: '#FFB5B5',
          200: '#FF8282',
          300: '#FF4F4F',
          400: '#FF1C1C',
          500: '#FF3B3B',
          600: '#CC2F2F',
          700: '#992323',
          800: '#661818',
          900: '#330C0C',
        },
        'accent-green': {
          DEFAULT: '#00FF88',
          50: '#E6FFF0',
          100: '#B3FFD6',
          200: '#80FFBC',
          300: '#4DFFA2',
          400: '#1AFF88',
          500: '#00FF88',
          600: '#00CC6D',
          700: '#009952',
          800: '#006637',
          900: '#00331C',
        },
        // 深邃暗黑主题背景色系
        'dark-bg': {
          primary: '#0A0E1A',    // 主背景色 - 深邃的深蓝黑
          secondary: '#111827',  // 次级背景色
          tertiary: '#1F2937',   // 第三级背景色
          surface: '#374151',    // 表面色 - 用于卡片等
        },
        // 边框和分割线颜色
        'dark-border': {
          DEFAULT: '#2D3748',
          light: '#4A5568',
          dark: '#1A202C',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', 'monospace'],
        sans: ['Inter', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      // 自定义动画
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(0, 217, 255, 0.5)' },
          '100%': { boxShadow: '0 0 20px rgba(0, 217, 255, 0.8)' },
        },
      },
    },
  },
  plugins: [],
}
