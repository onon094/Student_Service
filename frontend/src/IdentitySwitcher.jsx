import { useEffect, useRef, useState } from 'react'
import { ADMIN_URL, ASSISTANT_NAME, ROLE_LABEL } from './config.js'

/**
 * 右上角用户菜单（原身份切换器改造）
 * ------------------------------------------------------------
 * 严格权限下不允许「一键热切身份」——换身份必须重新登录，
 * 所以这里只保留：工作台、人工服务、管理后台（管理员）、退出。
 */
export default function IdentitySwitcher({ session, onHome, onSupport, onLogout }) {
  const [open, setOpen] = useState(false)
  const boxRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const onDown = e => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false) }
    const onKey = e => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const go = fn => { setOpen(false); fn() }

  return (
    <div className="id-switcher" ref={boxRef}>
      <button className="id-trigger" onClick={() => setOpen(v => !v)}>
        <span className="role-chip">{ROLE_LABEL[session.role]}</span>
        <b>{session.realName}</b>
        <span className="caret">{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div className="id-menu user-menu">
          <div className="id-menu-head">
            {ROLE_LABEL[session.role]} · {session.realName}
            <small>{session.department}{session.employeeRole ? ' · ' + session.employeeRole : ''}</small>
          </div>

          <button className="id-menu-item" onClick={() => go(onHome)}>
            <span className="id-menu-role">工作台</span>
            <span className="id-menu-desc">回到本身份的功能入口</span>
          </button>
          <button className="id-menu-item" onClick={() => go(onSupport)}>
            <span className="id-menu-role">人工服务</span>
            <span className="id-menu-desc">热线、留言与待办</span>
          </button>

          {session.role === 'admin' && (
            <a className="id-menu-link" href={ADMIN_URL} target="_blank" rel="noreferrer">
              打开管理后台 →
            </a>
          )}

          <div className="id-menu-sep" />

          <button className="id-menu-item danger" onClick={() => go(onLogout)}>
            <span className="id-menu-role">退出登录</span>
            <span className="id-menu-desc">换身份需重新登录</span>
          </button>

          <div className="id-menu-foot">当前助手：{ASSISTANT_NAME[session.role]}</div>
        </div>
      )}
    </div>
  )
}
