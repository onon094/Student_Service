import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 最小 Vite 配置：只用 React 插件，端口 5173
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0'
  }
})
