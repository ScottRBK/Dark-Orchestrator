import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, '.', '')

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: environment.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8099',
          changeOrigin: true,
        },
      },
    },
  }
})
