import { useEffect, useRef, useState } from 'react'
import BrandMark from './BrandMark.jsx'
import ChatWidget from './ChatWidget.jsx'
import IdentitySwitcher from './IdentitySwitcher.jsx'
import AppearanceMenu from './AppearanceMenu.jsx'
import ReviewMode from './ReviewMode.jsx'
import LoginDialog from './LoginDialog.jsx'
import Site from './Site.jsx'
import Workspace from './Workspace.jsx'
import Support from './Support.jsx'
import { KEYS, ROLE_LABEL, SESSION_KEY } from './config.js'

/**
 * 粤教服务 · 对外官网 + 内部系统
 * ------------------------------------------------------------
 * 未登录 → 官网首页（公司介绍 / 业务 / 流程 / 成果 / 历程 / 联系表单）
 * 右上角「登录」→ 弹窗（学生 / 员工·老师）；没有账号的人直接看官网、问在线客服
 * 登录后 → 该身份工作区，菜单与数据范围由 roles.js 统一推导
 */
function veilGradient(v) {
  return `linear-gradient(180deg,
    rgba(6,10,26,${(v * 0.72).toFixed(2)}) 0%,
    rgba(6,10,26,${v.toFixed(2)}) 55%,
    rgba(4,8,20,${Math.min(v + 0.14, 0.95).toFixed(2)}) 100%)`
}

// 官网右下角「在线客服」窗口用的会话：只用于调客服应用，
// 不是可登录身份（访客不再有独立工作台）。
const SERVICE_SESSION = {
  role: 'guest', userId: 0, username: 'guest', realName: '访客',
  userType: 'GUEST', employeeRole: null, department: '', key: KEYS.guest
}

// ?login=student|employee 直接打开登录弹窗（便于分发与演示）
const LOGIN_PARAM = new URLSearchParams(location.search).get('login')
const LOGIN_ROLES = ['student', 'employee', 'teacher']
// ?view=projects 可直接打开某个功能页（便于演示与截图）
const VIEW_PARAM = new URLSearchParams(location.search).get('view')

export default function App() {
  const stageRef = useRef(null)
  const toastTimer = useRef(null)

  const [session, setSession] = useState(() => {
    try {
      const s = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null')
      // 只认学生 / 员工（老师与管理员都属于员工体系）。
      // 旧版本存下的「访客」身份直接清掉，回官网首页。
      const valid = s && ['student', 'employee', 'teacher', 'admin'].includes(s.role)
      if (!valid && s) localStorage.removeItem(SESSION_KEY)
      return valid ? s : null
    } catch { return null }
  })
  const [stage, setStage] = useState(() => (session ? 'app' : 'site'))
  const [loginOpen, setLoginOpen] = useState(() => LOGIN_ROLES.includes(LOGIN_PARAM))
  const [loginRole, setLoginRole] = useState(
    LOGIN_ROLES.includes(LOGIN_PARAM) ? LOGIN_PARAM : 'student'
  )
  const [view, setView] = useState(VIEW_PARAM || 'home')
  const [toast, setToast] = useState('')
  // 批注：左下角常驻按钮，所有页面共用；?review=1 仍可直接进
  const [review, setReview] = useState(() => /[?&]review=1/.test(location.search))

  // 外观
  const [bgMode, setBgMode] = useState('photo')
  const [light, setLight] = useState(false)
  const [veil, setVeil] = useState(0.68)
  const [strength, setStrength] = useState(30)
  const [blur, setBlur] = useState(0.09)

  const photo = bgMode === 'photo'
  const stageClass = 'stage ' + (photo ? 'stage-photo' : light ? 'stage-light' : 'stage-dark')

  const showToast = msg => {
    setToast(msg)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(''), 2800)
  }
  useEffect(() => () => clearTimeout(toastTimer.current), [])

  const openReview = () => {
    setReview(true)
    window.dispatchEvent(new CustomEvent('yuejiao-close-chat'))
  }
  const closeReview = () => {
    setReview(false)
    history.replaceState(null, '', location.pathname + location.hash)
  }
  // 外观菜单里的「页面批注」也走同一条路（不再刷新页面）
  useEffect(() => {
    const open = () => {
      setReview(true)
      window.dispatchEvent(new CustomEvent('yuejiao-close-chat'))
    }
    window.addEventListener('yuejiao-review-open', open)
    return () => window.removeEventListener('yuejiao-review-open', open)
  }, [])

  const glass = {
    mouseContainer: stageRef,
    displacementScale: strength,
    blurAmount: blur,
    saturation: 130,
    aberrationIntensity: 1.4,
    elasticity: 0.2,
    cornerRadius: 22,
    overLight: !photo && light,
    mode: 'standard'
  }

  const backdrop = (
    <>
      {photo ? (
        <>
          <div className="bg-photo" />
          <div className="bg-veil" style={{ background: veilGradient(veil) }} />
        </>
      ) : (
        <>
          <div className="orb orb-1" /><div className="orb orb-2" /><div className="orb orb-3" />
          <div className="bg-word">YUEJIAO · STUDY ABROAD</div>
        </>
      )}
      <div className="bg-grid" />
    </>
  )
  const toastNode = toast ? <div className="toast">{toast}</div> : null

  const handleLogin = s => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(s))
    setSession(s)
    setView('home')
    setStage('app')
    setLoginOpen(false)
    showToast(`欢迎，${ROLE_LABEL[s.role]} · ${s.realName}`)
  }

  const handleLogout = () => {
    localStorage.removeItem(SESSION_KEY)
    setSession(null)
    setView('home')
    setStage('site')
    showToast('已退出登录')
  }

  // 任何接口返回 401（令牌过期）都会触发这里，统一回官网并要求重新登录
  useEffect(() => {
    const onExpired = () => {
      setSession(null)
      setStage('site')
      showToast('登录已过期，请重新登录')
    }
    window.addEventListener('yuejiao-logout', onExpired)
    return () => window.removeEventListener('yuejiao-logout', onExpired)
  }, [])

  const askChat = (text, send = true) => {
    window.dispatchEvent(new CustomEvent('yuejiao-ask', { detail: { text: text || '', send } }))
  }

  // ============ 未登录：官网 ============
  if (stage === 'site') {
    return (
      <div ref={stageRef} className={stageClass}>
        {backdrop}
        {toastNode}

        <Site
          onLogin={() => setLoginOpen(true)}
          onAsk={askChat}
        />

        <LoginDialog
          open={loginOpen}
          onClose={() => setLoginOpen(false)}
          glass={glass}
          onLogin={handleLogin}
          onContact={() => {
            setLoginOpen(false)
            setTimeout(() => document.querySelector('#contact')?.scrollIntoView({ behavior: 'smooth' }), 90)
          }}
          initialRole={loginRole}
        />
        {/* 官网右下角客服窗口：用客服应用作答，不涉及登录身份 */}
        <ChatWidget session={SERVICE_SESSION} />
        <ReviewMode open={review} onOpen={openReview} onClose={closeReview} />
      </div>
    )
  }

  // ============ 已登录：系统内 ============
  return (
    <div ref={stageRef} className={stageClass}>
      {backdrop}
      {toastNode}

      <div className="wrap">
        <div className="nav-wrap">
          <div className="nav-glass">
            <nav className="nav">
              <div className="brand">
                <BrandMark size={30} />
                <span>粤教服务</span>
              </div>

              <div className="nav-spacer" />

              <div className="nav-right">
                <button className="nav-cta" onClick={() => askChat('', false)}>问助手</button>
                <AppearanceMenu
                  bgMode={bgMode} setBgMode={setBgMode}
                  light={light} setLight={setLight}
                  veil={veil} setVeil={setVeil}
                  strength={strength} setStrength={setStrength}
                  blur={blur} setBlur={setBlur}
                />
                <IdentitySwitcher
                  session={session}
                  onHome={() => setView('home')}
                  onSupport={() => setView('support')}
                  onLogout={handleLogout}
                />
              </div>
            </nav>
          </div>
        </div>

        {view === 'support' ? (
          <>
            <div className="crumb">
              <button onClick={() => setView('home')}>← 工作台</button>
              <span>/</span><b>人工服务</b>
            </div>
            <Support session={session} onGo={setView} />
          </>
        ) : (
          <Workspace session={session} view={view} setView={setView} />
        )}

        <footer className="footer">
          粤教服务 · {ROLE_LABEL[session.role]}视图 · 数据来自本机 FastAPI，问答由 Dify 承载
        </footer>
        <ChatWidget session={session} />
      </div>

      <ReviewMode open={review} onOpen={openReview} onClose={closeReview} />
    </div>
  )
}
