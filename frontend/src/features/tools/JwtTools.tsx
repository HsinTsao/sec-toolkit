import { useState, useMemo, useCallback, useEffect, useRef, type TextareaHTMLAttributes } from 'react'
import { ToolCard, ToolButton, ToolSelect } from '@/components/ui/ToolCard'
import { toolsApi } from '@/lib/api'
import { useToolStore } from '@/stores/toolStore'
import { KeyRound, ShieldCheck, AlertTriangle, ArrowDown, ArrowUp, RefreshCw, Copy, Check } from 'lucide-react'
import toast from 'react-hot-toast'
import { cn, copyToClipboard } from '@/lib/utils'

function AutoTextarea({ value, minRows = 3, className, ...props }: { minRows?: number } & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    const lineHeight = parseFloat(getComputedStyle(el).lineHeight) || 20
    const minH = lineHeight * minRows + 24 // 24px for padding
    el.style.height = `${Math.max(el.scrollHeight, minH)}px`
  }, [value, minRows])
  return <textarea ref={ref} value={value} className={cn('overflow-hidden', className)} {...props} />
}

type AlgorithmType = 'symmetric' | 'RSA' | 'EC'

const ALGORITHM_OPTIONS = [
  { value: 'HS256', label: 'HS256 - HMAC SHA-256', type: 'symmetric' as AlgorithmType },
  { value: 'HS384', label: 'HS384 - HMAC SHA-384', type: 'symmetric' as AlgorithmType },
  { value: 'HS512', label: 'HS512 - HMAC SHA-512', type: 'symmetric' as AlgorithmType },
  { value: 'RS256', label: 'RS256 - RSA SHA-256', type: 'RSA' as AlgorithmType },
  { value: 'RS384', label: 'RS384 - RSA SHA-384', type: 'RSA' as AlgorithmType },
  { value: 'RS512', label: 'RS512 - RSA SHA-512', type: 'RSA' as AlgorithmType },
  { value: 'PS256', label: 'PS256 - RSA-PSS SHA-256', type: 'RSA' as AlgorithmType },
  { value: 'PS384', label: 'PS384 - RSA-PSS SHA-384', type: 'RSA' as AlgorithmType },
  { value: 'PS512', label: 'PS512 - RSA-PSS SHA-512', type: 'RSA' as AlgorithmType },
  { value: 'ES256', label: 'ES256 - ECDSA P-256', type: 'EC' as AlgorithmType },
  { value: 'ES384', label: 'ES384 - ECDSA P-384', type: 'EC' as AlgorithmType },
  { value: 'ES512', label: 'ES512 - ECDSA P-521', type: 'EC' as AlgorithmType },
]

const RSA_KEY_SIZE_OPTIONS = [
  { value: '2048', label: '2048 位' },
  { value: '3072', label: '3072 位' },
  { value: '4096', label: '4096 位' },
]

const DEFAULT_HMAC_SECRET = 'your-256-bit-secret'
const KNOWN_ALGORITHMS = new Set(ALGORITHM_OPTIONS.map(a => a.value))

function getAlgorithmType(algorithm: string): AlgorithmType {
  return ALGORITHM_OPTIONS.find(a => a.value === algorithm)?.type ?? 'symmetric'
}

function tryParseJson(str: string): object | null {
  try { return JSON.parse(str) } catch { return null }
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    await copyToClipboard(text)
    setCopied(true)
    toast.success('已复制')
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={handleCopy}
      disabled={!text}
      className="flex items-center gap-1 px-2 py-1 text-xs text-theme-muted hover:text-theme-primary disabled:opacity-50"
    >
      {copied ? <><Check className="w-3 h-3" />已复制</> : <><Copy className="w-3 h-3" />复制</>}
    </button>
  )
}

export default function JwtTools() {
  const { addRecentTool } = useToolStore()

  const [token, setToken] = useState('')
  const [header, setHeader] = useState('{\n  "alg": "HS256",\n  "typ": "JWT"\n}')
  const [payload, setPayload] = useState('{\n  "sub": "1234567890",\n  "name": "John Doe",\n  "iat": 1516239022\n}')
  const [tokenInfo, setTokenInfo] = useState('')
  const [algorithm, setAlgorithm] = useState('HS256')
  const [secret, setSecret] = useState(DEFAULT_HMAC_SECRET)
  const [privateKey, setPrivateKey] = useState('')
  const [publicKey, setPublicKey] = useState('')
  const [rsaKeySize, setRsaKeySize] = useState('2048')
  const [loading, setLoading] = useState('')

  // 验证状态
  const [verifyToken, setVerifyToken] = useState('')
  const [verifyAlgorithm, setVerifyAlgorithm] = useState('HS256')
  const [verifyKey, setVerifyKey] = useState('')
  const [verifyResult, setVerifyResult] = useState<{ valid: boolean; payload?: object; error?: string } | null>(null)

  const algType = useMemo(() => getAlgorithmType(algorithm), [algorithm])
  const verifyAlgType = useMemo(() => getAlgorithmType(verifyAlgorithm), [verifyAlgorithm])
  const isGeneratingRef = useRef(false)

  const generateKeypair = useCallback(async (alg: string, target: 'main' | 'verify') => {
    if (isGeneratingRef.current) return
    isGeneratingRef.current = true
    const algT = getAlgorithmType(alg)
    const loadingKey = target === 'main' ? 'keygen' : 'keygen-verify'
    setLoading(loadingKey)
    try {
      const keySize = algT === 'RSA' ? parseInt(rsaKeySize) : 2048
      const { data } = await toolsApi.jwtGenerateKeys(alg, keySize)
      if (data.error) { toast.error(data.error); return }
      if (target === 'main') {
        setPrivateKey(data.private_key)
        setPublicKey(data.public_key)
      } else {
        setVerifyKey(data.public_key)
      }
    } catch {
      toast.error('密钥生成失败')
    } finally {
      setLoading('')
      isGeneratingRef.current = false
    }
  }, [rsaKeySize])

  // 切换算法时自动设置默认密钥
  const handleAlgorithmChange = useCallback((newAlg: string) => {
    setAlgorithm(newAlg)
    // 同步 header 中的 alg 字段
    const parsed = tryParseJson(header)
    if (parsed) {
      const updated = { ...parsed, alg: newAlg }
      setHeader(JSON.stringify(updated, null, 2))
    }
    const newType = getAlgorithmType(newAlg)
    if (newType === 'symmetric') {
      if (!secret) setSecret(DEFAULT_HMAC_SECRET)
    } else {
      // 非对称切换时，如果当前无私钥则自动生成
      if (!privateKey || getAlgorithmType(algorithm) !== newType) {
        generateKeypair(newAlg, 'main')
      }
    }
  }, [header, secret, privateKey, algorithm, generateKeypair])

  // 解码: token → header + payload
  const handleDecode = async () => {
    if (!token.trim()) { toast.error('请输入 JWT Token'); return }
    setLoading('decode')
    try {
      const { data } = await toolsApi.jwtDecode(token)
      if (data.error) { toast.error(data.error); return }

      setHeader(JSON.stringify(data.header, null, 2))
      setPayload(JSON.stringify(data.payload, null, 2))

      // 从 header 中自动检测算法
      const detectedAlg = data.header?.alg
      if (detectedAlg && KNOWN_ALGORITHMS.has(detectedAlg)) {
        setAlgorithm(detectedAlg)
        const detectedType = getAlgorithmType(detectedAlg)
        if (detectedType === 'symmetric') {
          if (!secret) setSecret(DEFAULT_HMAC_SECRET)
        } else if (!privateKey || getAlgorithmType(algorithm) !== detectedType) {
          await generateKeypair(detectedAlg, 'main')
        }
      }

      let info = ''
      if (data.expiration) {
        if (data.expiration.exp) {
          info += `过期: ${data.expiration.exp} (${data.expiration.expired ? '已过期' : '未过期'})`
        }
        if (data.expiration.iat) {
          info += info ? ' · ' : ''
          info += `签发: ${data.expiration.iat}`
        }
      }
      setTokenInfo(info)

      // 同时填入验证区
      setVerifyToken(token)
      if (detectedAlg && KNOWN_ALGORITHMS.has(detectedAlg)) {
        setVerifyAlgorithm(detectedAlg)
      }

      addRecentTool('jwt')
    } catch {
      toast.error('解码失败')
    } finally {
      setLoading('')
    }
  }

  // 编码: header + payload + key → token
  const handleEncode = async () => {
    const parsedPayload = tryParseJson(payload)
    if (!parsedPayload) { toast.error('Payload 不是有效的 JSON'); return }

    const isAsymmetric = algType !== 'symmetric'
    const signingKey = isAsymmetric ? privateKey : secret

    if (!signingKey.trim()) {
      toast.error(isAsymmetric ? '请输入或生成私钥' : '请输入 Secret')
      return
    }

    setLoading('encode')
    try {
      const parsedHeader = tryParseJson(header)
      const { data } = await toolsApi.jwtEncode(parsedPayload, signingKey, algorithm, parsedHeader || undefined)
      if (data.result?.startsWith('错误:')) {
        toast.error(data.result)
      } else {
        setToken(data.result)
        // 自动填入验证区
        setVerifyToken(data.result)
        setVerifyAlgorithm(algorithm)
        if (isAsymmetric && publicKey) {
          setVerifyKey(publicKey)
        } else if (!isAsymmetric) {
          setVerifyKey(secret)
        }
        toast.success('JWT 已生成')
      }
      addRecentTool('jwt')
    } catch {
      toast.error('编码失败')
    } finally {
      setLoading('')
    }
  }

  // 编辑 header 时同步算法选择器
  const handleHeaderChange = (val: string) => {
    setHeader(val)
    const parsed = tryParseJson(val)
    if (parsed && (parsed as Record<string, unknown>).alg) {
      const alg = (parsed as Record<string, unknown>).alg as string
      if (KNOWN_ALGORITHMS.has(alg) && alg !== algorithm) {
        setAlgorithm(alg)
        const newType = getAlgorithmType(alg)
        if (newType !== 'symmetric' && (!privateKey || getAlgorithmType(algorithm) !== newType)) {
          generateKeypair(alg, 'main')
        }
      }
    }
  }

  // 验证
  const handleVerify = async () => {
    if (!verifyToken.trim()) { toast.error('请输入 JWT Token'); return }
    const isAsymmetric = verifyAlgType !== 'symmetric'
    if (!verifyKey.trim()) {
      toast.error(isAsymmetric ? '请输入公钥' : '请输入 Secret')
      return
    }
    setLoading('verify')
    try {
      const { data } = await toolsApi.jwtVerify(verifyToken, verifyKey, verifyAlgorithm)
      setVerifyResult(data)
      addRecentTool('jwt')
    } catch {
      toast.error('验证失败')
    } finally {
      setLoading('')
    }
  }

  // 验证区域算法切换 - 非对称时自动填默认公钥
  useEffect(() => {
    if (verifyAlgType !== 'symmetric' && !verifyKey) {
      if (publicKey && getAlgorithmType(algorithm) === verifyAlgType) {
        setVerifyKey(publicKey)
      }
    }
  }, [verifyAlgorithm])

  return (
    <div className="space-y-6 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-theme-text">JWT 工具</h1>
        <p className="text-theme-muted mt-1">
          解码、编辑、重新签名，支持 HMAC / RSA / ECDSA 算法
        </p>
      </div>

      {/* JWT 调试器 */}
      <ToolCard title="JWT 调试器" toolKey="jwt-debugger">
        <div className="space-y-4">
          {/* Token 输入区 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-theme-text">Encoded Token</label>
              <CopyButton text={token} />
            </div>
            <AutoTextarea
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="粘贴 JWT Token 后点击「解码」，或在下方编辑 Header / Payload 后点击「编码签名」生成 Token"
              minRows={3}
              className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-sm resize-none focus:outline-none focus:border-theme-primary text-orange-400/90"
            />
          </div>

          {/* 双向操作按钮 */}
          <div className="flex items-center gap-3">
            <ToolButton onClick={handleDecode} loading={loading === 'decode'} className="flex-1">
              <ArrowDown className="w-4 h-4 mr-1" />
              解码
            </ToolButton>
            <ToolButton onClick={handleEncode} loading={loading === 'encode'} variant="secondary" className="flex-1">
              <ArrowUp className="w-4 h-4 mr-1" />
              编码签名
            </ToolButton>
          </div>

          {/* Token 信息条 */}
          {tokenInfo && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-theme-bg border border-theme-border rounded-lg text-xs text-theme-muted">
              <span>{tokenInfo}</span>
            </div>
          )}

          {/* Header + Payload 编辑区 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-theme-text">
                  Header
                  <span className="ml-2 text-xs font-normal text-sky-400">{algorithm}</span>
                </label>
                <CopyButton text={header} />
              </div>
              <AutoTextarea
                value={header}
                onChange={(e) => handleHeaderChange(e.target.value)}
                minRows={4}
                className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-sm resize-none focus:outline-none focus:border-theme-primary text-sky-400/80"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-theme-text">Payload</label>
                <CopyButton text={payload} />
              </div>
              <AutoTextarea
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
                minRows={4}
                className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-sm resize-none focus:outline-none focus:border-theme-primary text-purple-400/80"
              />
            </div>
          </div>

          {/* 签名配置区 */}
          <div className="border-t border-theme-border pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-theme-text">签名配置</label>
              {algType !== 'symmetric' && (
                <div className="flex items-center gap-2 text-xs text-blue-400">
                  <KeyRound className="w-3.5 h-3.5" />
                  非对称算法：私钥签名 / 公钥验证
                </div>
              )}
            </div>

            <div className={cn('grid gap-4', algType === 'RSA' ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1')}>
              <ToolSelect
                label="算法"
                value={algorithm}
                onChange={handleAlgorithmChange}
                options={ALGORITHM_OPTIONS}
              />
              {algType === 'RSA' && (
                <ToolSelect
                  label="RSA 密钥长度"
                  value={rsaKeySize}
                  onChange={setRsaKeySize}
                  options={RSA_KEY_SIZE_OPTIONS}
                />
              )}
            </div>

            {/* 密钥输入 */}
            {algType === 'symmetric' ? (
              <div>
                <label className="block text-sm text-theme-muted mb-2">Secret</label>
                <input
                  type="text"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  placeholder={DEFAULT_HMAC_SECRET}
                  className="w-full"
                />
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm text-theme-muted">私钥 <span className="text-xs">(签名用)</span></label>
                    <button
                      onClick={() => generateKeypair(algorithm, 'main')}
                      disabled={loading === 'keygen'}
                      className="flex items-center gap-1 px-2 py-1 text-xs text-theme-primary hover:text-theme-primary/80 disabled:opacity-50"
                    >
                      <RefreshCw className={cn('w-3 h-3', loading === 'keygen' && 'animate-spin')} />
                      重新生成密钥对
                    </button>
                  </div>
                  <AutoTextarea
                    value={privateKey}
                    onChange={(e) => setPrivateKey(e.target.value)}
                    placeholder={loading === 'keygen' ? '正在生成密钥...' : '-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----'}
                    minRows={6}
                    className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-xs resize-none focus:outline-none focus:border-theme-primary"
                  />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm text-theme-muted">公钥 <span className="text-xs">(验证用)</span></label>
                    <CopyButton text={publicKey} />
                  </div>
                  <AutoTextarea
                    value={publicKey}
                    onChange={(e) => setPublicKey(e.target.value)}
                    placeholder="公钥将在生成密钥对时自动填入"
                    minRows={6}
                    readOnly
                    className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-xs resize-none opacity-80"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </ToolCard>

      {/* JWT 验证 */}
      <ToolCard title="JWT 签名验证" toolKey="jwt-verify">
        <div className="space-y-4">
          <ToolSelect
            label="验证算法"
            value={verifyAlgorithm}
            onChange={(v) => {
              setVerifyAlgorithm(v)
              setVerifyResult(null)
              const newType = getAlgorithmType(v)
              if (newType === 'symmetric') {
                if (!verifyKey) setVerifyKey(DEFAULT_HMAC_SECRET)
              } else if (publicKey && getAlgorithmType(algorithm) === newType) {
                setVerifyKey(publicKey)
              } else {
                setVerifyKey('')
              }
            }}
            options={ALGORITHM_OPTIONS}
          />

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-theme-muted">JWT Token</label>
              {token && verifyToken !== token && (
                <button
                  onClick={() => { setVerifyToken(token); setVerifyResult(null) }}
                  className="text-xs text-theme-primary hover:text-theme-primary/80"
                >
                  使用调试器中的 Token
                </button>
              )}
            </div>
            <AutoTextarea
              value={verifyToken}
              onChange={(e) => { setVerifyToken(e.target.value); setVerifyResult(null) }}
              placeholder="粘贴需要验证的 JWT Token..."
              minRows={3}
              className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-sm resize-none focus:outline-none focus:border-theme-primary"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-theme-muted">
                {verifyAlgType !== 'symmetric' ? '公钥 (PEM)' : 'Secret'}
              </label>
              {verifyAlgType !== 'symmetric' && publicKey && verifyKey !== publicKey && (
                <button
                  onClick={() => setVerifyKey(publicKey)}
                  className="text-xs text-theme-primary hover:text-theme-primary/80"
                >
                  使用调试器中的公钥
                </button>
              )}
            </div>
            {verifyAlgType !== 'symmetric' ? (
              <AutoTextarea
                value={verifyKey}
                onChange={(e) => { setVerifyKey(e.target.value); setVerifyResult(null) }}
                placeholder="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
                minRows={4}
                className="w-full bg-theme-bg border border-theme-border rounded-lg px-4 py-3 font-mono text-xs resize-none focus:outline-none focus:border-theme-primary"
              />
            ) : (
              <input
                type="text"
                value={verifyKey}
                onChange={(e) => { setVerifyKey(e.target.value); setVerifyResult(null) }}
                placeholder={DEFAULT_HMAC_SECRET}
                className="w-full"
              />
            )}
          </div>

          <ToolButton onClick={handleVerify} loading={loading === 'verify'}>
            <ShieldCheck className="w-4 h-4 mr-1" />
            验证签名
          </ToolButton>

          {verifyResult && (
            <div
              className={cn(
                'rounded-lg border p-4',
                verifyResult.valid
                  ? 'bg-green-500/10 border-green-500/30'
                  : 'bg-red-500/10 border-red-500/30'
              )}
            >
              <div className="flex items-center gap-2">
                {verifyResult.valid ? (
                  <>
                    <ShieldCheck className="w-5 h-5 text-green-400" />
                    <span className="font-semibold text-green-400">签名有效</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-5 h-5 text-red-400" />
                    <span className="font-semibold text-red-400">签名无效</span>
                  </>
                )}
              </div>
              {verifyResult.valid && verifyResult.payload && (
                <pre className="mt-3 font-mono text-sm text-theme-text bg-theme-bg/50 rounded p-3 overflow-auto">
                  {JSON.stringify(verifyResult.payload, null, 2)}
                </pre>
              )}
              {!verifyResult.valid && verifyResult.error && (
                <p className="mt-2 text-sm text-red-300">{verifyResult.error}</p>
              )}
            </div>
          )}
        </div>
      </ToolCard>
    </div>
  )
}
