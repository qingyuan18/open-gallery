import tailwindcss from '@tailwindcss/vite'
import { TanStackRouterVite } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { defineConfig } from 'vite'

const PORT = 57988

// https://vite.dev/config/
export default defineConfig(() => {
  return {
    plugins: [
      TanStackRouterVite({
        target: 'react',
        autoCodeSplitting: true,
        generatedRouteTree: 'src/route-tree.gen.ts',
      }),
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': path.resolve('./src'),
      },
    },
    server: {
      host: true,  // 在Vite 6.x中，true表示监听所有接口
      port: 5174,
      strictPort: false,
      allowedHosts: [
        'localhost',
        '127.0.0.1',
        '0.0.0.0',
        'ec2-52-24-176-86.us-west-2.compute.amazonaws.com',
        '.compute.amazonaws.com',  // 允许所有AWS EC2域名
        '.amazonaws.com'           // 允许所有AWS域名
      ],
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${PORT}`,
          changeOrigin: true,
        },
        '/ws': {
          target: `ws://127.0.0.1:${PORT}`,
          ws: true,
        },
      },
    },
  }
})
