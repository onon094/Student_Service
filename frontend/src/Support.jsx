import { useState } from 'react'
import { api, post, useLoad, Notice } from './ui.jsx'
import { ADMIN_URL } from './config.js'

/**
 * 人工服务（原「人工服务」区块）
 * ------------------------------------------------------------
 * 不再有区块标题，也不再解释「什么事该找人工」。
 * 学生：联系方式 + 留言；员工：联系方式 + 业务看板（客户进度 + 心理预警）。
 * 员工侧不放「处理入口」，因为这些入口工作台里已经有了，重复反而乱。
 */
const CONTACT = [
  { k: '服务热线', v: '400-880-6688', note: '工作日 9:00–18:30' },
  { k: '服务邮箱', v: 'service@yuejiao-edu.com', note: '投诉与材料补充' },
  { k: '办公地址', v: '广州市天河区珠江新城华夏路 8 号 粤教大厦 18 层', note: '来访请提前预约' }
]

const LEAD_STATUS = ['新增意向', '跟进中', '已签约', '已流失']
const ALERT_STATUS = ['未处理', '跟进中', '已解除']

export default function Support({ session, onGo }) {
  const isStudent = session.role === 'student'
  const isStaff = ['employee', 'teacher', 'admin'].includes(session.role)

  const [draft, setDraft] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const leads = useLoad(() => (isStaff ? api('/api/employee/leads') : Promise.resolve([])), [isStaff])
  const alerts = useLoad(() => (isStaff ? api('/api/psych/alerts') : Promise.resolve([])), [isStaff])

  const leadRows = Array.isArray(leads.data) ? leads.data : []
  const alertRows = Array.isArray(alerts.data) ? alerts.data : []

  const countBy = (rows, key, list) => list.map(s => ({
    name: s,
    value: rows.filter(x => x[key] === s).length
  }))

  const leadStats = countBy(leadRows, 'status', LEAD_STATUS)
  const alertStats = countBy(alertRows, 'status', ALERT_STATUS)

  const submit = async () => {
    if (!draft.trim() || busy) return
    setBusy(true); setMsg('')
    try {
      const d = await post('/api/student/feedback', { student_id: session.userId, content: draft.trim() })
      setDraft('')
      setMsg(`已提交工单 #${d.id}，处理结果会出现在「售后反馈」里`)
    } catch (e) {
      setMsg('提交失败：' + e.message)
    } finally { setBusy(false) }
  }

  return (
    <section className="section support-section" id="support">
      <div className="support-grid">
        <aside className="support-contact">
          <div className="sup-lines">
            {CONTACT.map(c => (
              <div className="sup-line" key={c.k}>
                <span>{c.k}</span>
                <b>{c.v}</b>
                <small>{c.note}</small>
              </div>
            ))}
          </div>
          {session.role === 'admin' && (
            <a className="admin-link" href={ADMIN_URL} target="_blank" rel="noreferrer">
              打开管理后台 →
            </a>
          )}
        </aside>

        <div className="support-main">
          <Notice text={msg} />

          {isStudent && (
            <div className="sup-block sup-block-fill">
              <h3>给老师留言</h3>
              <textarea className="sup-textarea sup-textarea-lg" value={draft}
                onChange={e => setDraft(e.target.value)}
                placeholder="写清时间、地点、诉求，例如：宿舍空调从周一开始不制冷，已报修两次仍未处理。" />
              <div className="link-row">
                <span className="hint-text">{draft.length} 字</span>
                <button className="sup-primary" onClick={submit} disabled={busy || !draft.trim()}>
                  {busy ? '提交中…' : '提交工单'}
                </button>
              </div>
            </div>
          )}

          {isStaff && (
            <div className="staff-board">
              <div className="board-block">
                <h4>
                  意向客户进度
                  <button className="board-more" onClick={() => onGo('leads')}>查看全部 →</button>
                </h4>
                <div className="board-stats">
                  {leadStats.map(s => (
                    <div key={s.name}><b>{s.value}</b><span>{s.name}</span></div>
                  ))}
                </div>
                <ul className="board-list">
                  {leadRows.slice(0, 3).map(l => (
                    <li key={l.id}>
                      <span>{l.customer_name}</span>
                      <span className="board-tag">{l.status}</span>
                    </li>
                  ))}
                  {leadRows.length === 0 && !leads.loading && <li><span className="hint-text">暂无客户</span></li>}
                </ul>
              </div>

              <div className="board-block">
                <h4>
                  学生心理状态
                  <button className="board-more" onClick={() => onGo('psych')}>查看全部 →</button>
                </h4>
                <div className="board-stats">
                  {alertStats.map(s => (
                    <div key={s.name}><b>{s.value}</b><span>{s.name}</span></div>
                  ))}
                </div>
                <ul className="board-list">
                  {alertRows.slice(0, 3).map(a => (
                    <li key={a.id}>
                      <span>{a.student_name || a.student_id} · {a.trigger_reason}</span>
                      <span className="board-tag">{a.status}</span>
                    </li>
                  ))}
                  {alertRows.length === 0 && !alerts.loading && <li><span className="hint-text">暂无预警</span></li>}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
