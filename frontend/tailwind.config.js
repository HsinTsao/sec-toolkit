/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 使用 CSS 变量实现主题切换
        theme: {
          bg: 'var(--color-bg)',
          card: 'var(--color-card)',
          border: 'var(--color-border)',
          primary: 'var(--color-primary)',
          secondary: 'var(--color-secondary)',
          accent: 'var(--color-accent)',
          warning: 'var(--color-warning)',
          danger: 'var(--color-danger)',
          success: 'var(--color-success)',
          text: 'var(--color-text)',
          muted: 'var(--color-muted)',
          strong: 'var(--color-strong)',
          code: 'var(--color-code)',
        },
        // 保留原有赛博朋克配色作为备用
        cyber: {
          bg: '#0a0e17',
          card: '#0d1321',
          border: '#1a2332',
          primary: '#00d4aa',
          secondary: '#7c3aed',
          accent: '#f472b6',
          warning: '#fbbf24',
          danger: '#ef4444',
          success: '#22c55e',
          text: '#e2e8f0',
          muted: '#64748b',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'glow': 'glow 2s ease-in-out infinite alternate',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px var(--color-primary), 0 0 10px var(--color-primary), 0 0 15px var(--color-primary)' },
          '100%': { boxShadow: '0 0 10px var(--color-primary), 0 0 20px var(--color-primary), 0 0 30px var(--color-primary)' },
        },
      },
      // Typography 插件自定义样式
      typography: {
        DEFAULT: {
          css: {
            '--tw-prose-body': 'var(--color-text)',
            '--tw-prose-headings': 'var(--color-text)',
            '--tw-prose-links': 'var(--color-primary)',
            '--tw-prose-bold': 'var(--color-text)',
            '--tw-prose-code': 'var(--color-text)',
            '--tw-prose-quotes': 'var(--color-muted)',
            '--tw-prose-quote-borders': 'var(--color-primary)',
            '--tw-prose-bullets': 'var(--color-muted)',
            '--tw-prose-counters': 'var(--color-muted)',
            '--tw-prose-th-borders': 'var(--color-border)',
            '--tw-prose-td-borders': 'var(--color-border)',
          },
        },
        invert: {
          css: {
            '--tw-prose-body': 'var(--color-text)',
            '--tw-prose-headings': 'var(--color-text)',
            '--tw-prose-links': 'var(--color-primary)',
            '--tw-prose-bold': 'var(--color-text)',
            '--tw-prose-code': 'var(--color-text)',
            '--tw-prose-quotes': 'var(--color-muted)',
            '--tw-prose-quote-borders': 'var(--color-primary)',
          },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
