import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  
  // 检查是否启用 HTTPS
  const enableHttps = env.VITE_HTTPS === 'true'
  
  // HTTPS 配置
  let httpsConfig: boolean | { key: Buffer; cert: Buffer } = false
  
  if (enableHttps) {
    const certDir = path.resolve(__dirname, '../certs')
    const keyPath = path.join(certDir, 'server.key')
    const certPath = path.join(certDir, 'server.crt')
    
    if (fs.existsSync(keyPath) && fs.existsSync(certPath)) {
      httpsConfig = {
        key: fs.readFileSync(keyPath),
        cert: fs.readFileSync(certPath),
      }
      console.log('🔒 HTTPS 已启用')
    } else {
      console.warn('⚠️ 未找到 SSL 证书，请先运行: ./scripts/generate-ssl-cert.sh')
      console.warn('   回退到 HTTP 模式')
    }
  }
  
  // 后端 API 地址
  const apiTarget = env.VITE_API_URL || (enableHttps ? 'https://localhost:8000' : 'http://localhost:8000')
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      host: true,
      https: httpsConfig,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          secure: false, // 允许自签名证书
          ws: true, // 支持 WebSocket（反弹 Shell 终端等）
          timeout: 60000, // 60 秒超时
          configure: (proxy) => {
            proxy.on('error', (err, req, res) => {
              console.error('[Proxy Error]', err.message)
            })
            proxy.on('proxyReq', (proxyReq, req) => {
              // 传递真实客户端 IP（OOB 回调等需要）
              const clientIp = req.headers['x-forwarded-for']?.split(',')[0]?.trim()
                || req.socket?.remoteAddress
                || (req as any).connection?.remoteAddress
              if (clientIp) {
                const forwarded = req.headers['x-forwarded-for'] || clientIp
                proxyReq.setHeader('X-Real-IP', clientIp)
                proxyReq.setHeader('X-Forwarded-For', forwarded)
              }
              if (req.headers['content-length']) {
                proxyReq.setHeader('Content-Length', req.headers['content-length'])
              }
            })
          },
        },
        '/c': {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
          timeout: 60000,
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq, req) => {
              // 传递真实客户端 IP（OOB 回调必须）
              const clientIp = req.headers['x-forwarded-for']?.split(',')[0]?.trim()
                || req.socket?.remoteAddress
                || (req as any).connection?.remoteAddress
              if (clientIp) {
                const forwarded = req.headers['x-forwarded-for'] || clientIp
                proxyReq.setHeader('X-Real-IP', clientIp)
                proxyReq.setHeader('X-Forwarded-For', forwarded)
              }
            })
          },
        },
      },
    },
    preview: {
      port: 4173,
      https: httpsConfig,
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
    },
  }
})
