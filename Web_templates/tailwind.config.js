/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,html}",
    "./*.{html,js}"
  ],
  theme: {
    extend: {
      colors: {
        // Background chính của toàn bộ trang
        background: {
          DEFAULT: '#0b1f3d', // Deep Midnight Navy
          dark: '#07152b',
        },
        // Màu container, card, bề mặt
        surface: {
          DEFAULT: '#13294b', // Card background chính
          hover: '#18335c',
          nested: '#0f2140', // Khung con (device item, memory item)
          cardDark: '#0b1220',
        },
        // Màu chữ
        text: {
          primary: '#ffffff',
          secondary: '#9ca3af', // Gray-400 cho subtext, hướng dẫn
          muted: '#6b7280',    // Gray-500
          light: '#dbe3ef',
        },
        // Màu điểm nhấn (Action, Brand Blue)
        primary: {
          DEFAULT: '#2563eb', // Blue 600
          hover: '#1d4ed8',   // Blue 700
          light: '#3b82f6',   // Blue 500
          glow: 'rgba(37, 99, 235, 0.4)',
        },
        // Màu trạng thái hệ thống
        status: {
          success: '#16a34a', // Connected badge
          warning: '#fbbf24', // VIP badge, gold alert
          danger: '#ef4444',  // Nút xóa, disconnected
          dangerHover: '#dc2626',
          info: '#60a5fa',
        },
        secondary: {
          DEFAULT: '#374151', // Nút phụ
          hover: '#4b5563',
        }
      },
      fontFamily: {
        sans: ["'Segoe UI'", "system-ui", "-apple-system", "sans-serif"],
      },
      fontSize: {
        'badge': ['11px', { lineHeight: '14px', fontWeight: '700' }],
        'caption': ['12px', { lineHeight: '16px' }],
        'sub': ['13px', { lineHeight: '18px' }],
        'body': ['14px', { lineHeight: '20px' }],
        'card-title': ['18px', { lineHeight: '24px', fontWeight: '700' }],
        'section-title': ['20px', { lineHeight: '28px', fontWeight: '700' }],
        'page-title': ['22px', { lineHeight: '30px', fontWeight: '700' }],
      },
      borderRadius: {
        'card': '14px',
        'card-sm': '10px',
        'control': '8px',   // Dành cho input & button
        'pill': '20px',      // Dành cho badge
      },
      boxShadow: {
        'primary-glow': '0 4px 12px rgba(37, 99, 235, 0.4)',
        'modal': '0 18px 50px rgba(0, 0, 0, 0.45)',
        'soft': '0 2px 8px rgba(0, 0, 0, 0.25)',
      }
    },
  },
  plugins: [],
}

