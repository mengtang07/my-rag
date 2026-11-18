import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 前端一律用相对路径 /api/...，开发走代理，生产同源反代。
      // 不要加 buffer —— 那会把 SSE 的流式响应攒成一坨，流式就没了。
      '/api': {
        target: 'http://localhost:8088',
        changeOrigin: true,
      },
    },
  },
})
