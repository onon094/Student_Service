import { useState } from 'react'
import LiquidGlass from 'liquid-glass-react'
import { API, KEYS, ROLE_HINT, ROLE_LABEL } from './config.js'
import { post } from './ui.jsx'
import BrandMark from './BrandMark.jsx'

/**
 * 单身份登录页 / 弹窗内表单
 * ------------------------------------------------------------
 * 账号密码交给后端校验（POST /api/identity/login），成功返回令牌；
 * 角色由后端根据账号判定，前端只做「这个账号该不该在本页登录」的提示。
 * 前端不再保存也不比对任何口令。
 */
const SAMPLES = {
  student: ['student_zhang', 'student_xu'],
  employee: ['teacher_chen', 'sales_lin', 'admin_sys']
}

export default function Login({ glass, role, onLogin, onBack, embedded = false, hideBack = false }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const samples = (SAMPLES[role] || []).join(' / ')
  const allowedRoles = role === 'employee' ? ['employee', 'admin'] : ['student']

  const submit = async () => {
    if (busy) return
    const name = username.trim()
    if (!name) return setError('请输入账号')
    if (!password) return setError('请输入密码')

    setBusy(true)
    setError('')
    try {
      const d = await post('/api/identity/login', { username: name, password })
      if (!allowedRoles.includes(d.role)) {
        return setError(`这是${ROLE_LABEL[role]}登录页，${name} 不是该身份账号`)
      }

      // 学生账号必须已签约（签约时才开通课程）：未开通的不允许进系统
      if (d.role === 'student') {
        const res = await fetch(`${API}/api/student/enrollments?student_id=${d.user.id}`, {
          headers: { Authorization: 'Bearer ' + d.token }
        })
        if (res.ok) {
          const enr = await res.json()
          if (!enr?.signed) {
            return setError('该账号还没有签约课程。请联系顾问签约，签约后会自动开通账号与课程。')
          }
        }
      }

      onLogin({
        role: d.role,
        userId: d.user.id,
        username: d.user.username,
        realName: d.user.real_name,
        userType: d.user.user_type,
        employeeRole: d.user.employee_role,
        department: d.user.department,
        key: KEYS[d.role],
        token: d.token
      })
    } catch (e) {
      let msg = e.message || '登录失败'
      // 后端返回的是 JSON 字符串，抽取出 detail
      try {
        const parsed = JSON.parse(msg)
        msg = parsed.detail || msg
      } catch { /* 保持原文 */ }
      setError(msg)
    } finally {
      setBusy(false)
    }
  }

  const card = (
    <div className="login-card">
      {!hideBack && <button className="back-link" onClick={onBack}>← 返回入口</button>}

      <div className="login-brand">
        <BrandMark size={38} />
        <div>
          <h1>{ROLE_LABEL[role]}登录</h1>
          <p>{ROLE_HINT[role]}</p>
        </div>
      </div>

      <label className="field">
        <span>账号</span>
        <input
          value={username}
          onChange={e => { setUsername(e.target.value); setError('') }}
          onKeyDown={e => { if (e.key === 'Enter') submit() }}
          placeholder={`请输入${ROLE_LABEL[role]}账号`}
          autoComplete="username"
        />
      </label>

      <label className="field">
        <span>密码</span>
        <input
          type="password"
          value={password}
          onChange={e => { setPassword(e.target.value); setError('') }}
          onKeyDown={e => { if (e.key === 'Enter') submit() }}
          placeholder="请输入密码"
          autoComplete="current-password"
        />
      </label>

      {error && <div className="login-error">{error}</div>}

      <button className="login-submit" onClick={submit} disabled={busy}>
        {busy ? '验证中…' : '登录 →'}
      </button>

      <div className="login-samples">
        <span>演示账号</span>
        <code>{samples || '（无）'}</code>
        <small>初始密码 <code>123456</code>；账号身份与当前登录页不符会被拒绝</small>
      </div>
    </div>
  )

  if (embedded) return card

  return (
    <div className="login-page">
      <div className="glass-slot">
        <LiquidGlass {...glass} padding="28px 30px">{card}</LiquidGlass>
      </div>
    </div>
  )
}
