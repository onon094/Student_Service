import { MENUS, DATA_SCOPE } from './roles.js'
import { ROLE_LABEL } from './config.js'
import { api, useLoad } from './ui.jsx'
import * as P from './panels.jsx'
import Support from './Support.jsx'

/**
 * 身份工作区
 * ------------------------------------------------------------
 * 菜单、卡片、功能页全部来自 roles.js 的 MENUS，
 * 顶部固定显示「数据范围」，让越权边界看得见。
 */
const PANELS = {
  leaves: P.LeavesPanel,
  feedback: P.FeedbackPanel,
  scores: P.ScoresPanel,
  psych: P.PsychPanel,
  leads: P.LeadsPanel,
  reports: P.ReportsPanel,
  events: P.EventsPanel,
  projects: P.ProjectsPanel,
  health: P.HealthPanel,
  consult: P.ConsultPanel,
  profile: P.ProfilePanel,
  recommend: P.RecommendPanel
}

export default function Workspace({ session, view, setView }) {
  const menu = MENUS[session.role] || []
  const current = menu.find(m => m.key === view)

  if (!current) return <Home session={session} setView={setView} />

  const Panel = PANELS[current.key]
  const scope = DATA_SCOPE[current.key]?.[session.role]

  return (
    <section className="workspace">
      <div className="crumb">
        <button onClick={() => setView('home')}>← 工作台</button>
        <span>/</span>
        <b>{current.label}</b>
      </div>

      <div className="view-head">
        <h2>{current.label}</h2>
        <p>{current.desc}</p>
        {scope && <div className="scope-note">数据范围：{scope}</div>}
      </div>

      <div className="chip-row menu-chips">
        {menu.map(m => (
          <button key={m.key} className={'chip' + (m.key === view ? ' on' : '')}
            onClick={() => setView(m.key)}>
            {m.label}
          </button>
        ))}
      </div>

      {Panel
        ? <Panel session={session} onGo={setView} />
        : <div className="sup-empty">该功能暂未开放</div>}
    </section>
  )
}

function Home({ session, setView }) {
  const menu = MENUS[session.role] || []
  // 待办直接放在头部：进工作台第一眼就知道有几件事等着处理
  const isStudent = session.role === 'student'
  const q = isStudent ? `?student_id=${session.userId}` : ''
  const leaves = useLoad(() => api('/api/student/leaves' + q), [q])
  const tickets = useLoad(() => api('/api/student/feedback' + q), [q])

  const pendingLeave = (leaves.data || []).filter(x => x.status === '待审批').length
  const pendingTicket = (tickets.data || []).filter(x => x.status === '待处理').length

  const meta = [
    ROLE_LABEL[session.role],
    session.department,
    session.employeeRole
  ].filter(Boolean).join(' · ')

  // 按卡片数量挑列数，保证最后一行是满的（避免右侧留一大块空白）
  const cols = menu.length % 4 === 0 ? 4 : menu.length % 3 === 0 ? 3 : 4

  return (
    <>
      <section className="workspace">
        <div className="welcome">
          <div className="welcome-id">
            <h1>{session.realName}</h1>
            <small>{meta}</small>
          </div>

          <div className="todo-bar">
            <button onClick={() => setView('leaves')} title="查看请假">
              <b>{pendingLeave}</b>
              <span>待审批请假</span>
            </button>
            <button onClick={() => setView('feedback')} title="查看工单">
              <b>{pendingTicket}</b>
              <span>{isStudent ? '待处理工单' : '待处理工单'}</span>
            </button>
          </div>
        </div>

        <div className="card-grid" data-cols={cols}>
          {menu.map(m => (
            <button key={m.key} className="fn-card" onClick={() => setView(m.key)}>
              <span className="fn-tag">{m.tag}</span>
              <b>{m.label}</b>
              <small>{m.desc}</small>
            </button>
          ))}
        </div>
      </section>

      <Support session={session} onGo={setView} />
    </>
  )
}

