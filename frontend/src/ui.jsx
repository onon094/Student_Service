import { useCallback, useEffect, useState } from 'react'
import { API, SESSION_KEY } from './config.js'

/** 从本地会话取令牌；没有就返回空对象（后端会回 401）。 */
function authHeaders() {
  try {
    const s = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null')
    return s?.token ? { Authorization: 'Bearer ' + s.token } : {}
  } catch {
    return {}
  }
}

// 匿名场景也会用到的公开接口：它们返回 401 时不算"登录过期"，不弹全局提示
const PUBLIC_PATHS = [
  '/api/identity/login', '/api/recommend', '/api/catalog/projects',
  '/api/catalog/events', '/api/health',
]

export async function api(path, opt = {}) {
  const headers = { ...authHeaders(), ...(opt.headers || {}) }
  const res = await fetch(API + path, { ...opt, headers })
  // 令牌失效：清掉本地会话并通知外层回官网
  // 注意：本地没有会话（匿名官网场景）或访问公开接口时不弹"登录已过期"，
  // 避免官网匿名提交被 401 误伤后弹出误导性的过期提示。
  if (res.status === 401) {
    const hasSession = !!localStorage.getItem(SESSION_KEY)
    const isPublic = PUBLIC_PATHS.some(p => path.startsWith(p)) || path.includes('/register')
    if (hasSession && !isPublic) {
      localStorage.removeItem(SESSION_KEY)
      window.dispatchEvent(new CustomEvent('yuejiao-logout'))
    }
  }
  if (!res.ok) {
    let msg = 'HTTP ' + res.status
    try {
      const t = await res.text()
      if (t) msg = t.slice(0, 140)
    } catch { /* ignore */ }
    throw new Error(msg)
  }
  return res.json().catch(() => null)
}

export const post = (path, body) => api(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body)
})

export const patch = (path, body) => api(path, {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body)
})

// DELETE 请求：删除类操作只给前端管理后台（真人）用，不暴露给 Dify 智能体
export const del = (path) => api(path, { method: 'DELETE' })

export function useLoad(loader, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const run = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await loader())
    } catch (e) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, deps)

  useEffect(() => { run() }, [run])
  return { data, error, loading, reload: run }
}

export function Badge({ text }) {
  const s = text || ''
  const cls = (s.includes('通过') || s.includes('解决') || s.includes('成交'))
    ? 'ok'
    : (s.includes('驳回') || s.includes('流失'))
      ? 'no'
      : 'wait'
  return <span className={'sup-status ' + cls}>{s || '—'}</span>
}

export function Table({ head, rows }) {
  return (
    <table className="sup-table">
      <thead><tr>{head.map(h => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{rows}</tbody>
    </table>
  )
}

export function Empty({ children }) {
  return <div className="sup-empty">{children || '暂无数据'}</div>
}

export function Loader({ error, loading }) {
  if (loading) return <div className="sup-empty">正在读取数据…</div>
  if (error) return <div className="sup-error">读取失败：{error}</div>
  return null
}

export function Notice({ text }) {
  if (!text) return null
  return <div className="sup-notice">{text}</div>
}

export function Field({ label, children, hint }) {
  return (
    <label className="fld">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}
