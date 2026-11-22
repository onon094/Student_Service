import { useEffect, useState } from 'react'
import Login from './Login.jsx'

/**
 * 登录弹窗
 * ------------------------------------------------------------
 * 官网首页右上角「登录」打开这里；内部不再有「选择进入方式」整页，
 * 只有两个 Tab：学生 / 员工（含老师与管理员）。
 * 没有账号的人不需要登录，官网本身就是公开入口。
 */
const TABS = [
  { key: 'student', label: '学生' },
  { key: 'employee', label: '老师' }
]

export default function LoginDialog({ open, onClose, glass, onLogin, onContact, initialRole }) {
  const [role, setRole] = useState(initialRole && initialRole !== 'guest' ? initialRole : 'student')

  useEffect(() => {
    if (open) setRole(initialRole && initialRole !== 'guest' ? initialRole : 'student')
  }, [open, initialRole])

  useEffect(() => {
    if (!open) return
    const onKey = e => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="dlg-mask" onMouseDown={onClose}>
      <div className="dlg-box" onMouseDown={e => e.stopPropagation()}>
        <button className="dlg-close" onClick={onClose} aria-label="关闭">✕</button>

        <div className="dlg-head">
          <h3>登录粤教服务</h3>
          <p>账号决定你能看到哪些功能与数据</p>
        </div>

        <div className="dlg-tabs">
          {TABS.map(t => (
            <button key={t.key} className={role === t.key ? 'on' : ''} onClick={() => setRole(t.key)}>
              {t.label}
            </button>
          ))}
        </div>

        <Login
          embedded
          hideBack
          glass={glass}
          role={role}
          onLogin={onLogin}
          onBack={() => {}}
        />

        <div className="dlg-foot">
          <button className="dlg-guest" onClick={onContact}>还没有账号？留个电话让顾问联系你 →</button>
          <small>管理员账号从「老师」进入，自动获得全部权限</small>
        </div>
      </div>
    </div>
  )
}
