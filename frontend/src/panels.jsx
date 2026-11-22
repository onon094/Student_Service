import { useEffect, useRef, useState } from 'react'
import { api, post, patch, del, useLoad, Badge, Table, Empty, Loader, Notice, Field } from './ui.jsx'
import { ADMIN_URL } from './config.js'
import { isStaff } from './roles.js'

// 情绪标签 / 风险等级 → 颜色；情绪历史按天汇总
function tagClass(tag = '') {
  if (tag.includes('高危')) return 'high'
  if (tag.includes('负面')) return 'bad'
  if (tag.includes('积极')) return 'good'
  return 'calm'
}

function riskClass(level = '') {
  if (level.includes('高')) return 'high'
  if (level.includes('中')) return 'mid'
  return 'low'
}

function groupByDay(history) {
  const map = {}
  ;(Array.isArray(history) ? history : []).forEach(h => {
    const date = (h.time || '').slice(0, 10)
    if (!date) return
    if (!map[date]) map[date] = []
    map[date].push(h)
  })
  return Object.entries(map)
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, items]) => {
      const sorted = items.slice().sort((x, y) => (x.time || '').localeCompare(y.time || ''))
      return { date, items: sorted, latest: sorted[sorted.length - 1] }
    })
}

/**
 * 各身份的功能面板
 * ------------------------------------------------------------
 * 每个面板内部先判断 session.role 再决定：能不能写、能看到谁的数据。
 * 菜单层隐藏只是第一道，这里是第二道（真正决定调用哪个参数）。
 */

const today = () => new Date().toISOString().slice(0, 10)

// 录入成绩时的候选项：尽量点选，不让人手打
const COURSE_PRESETS = ['Python', 'Mysql', 'Linux', '英语', '德语', '数学', '学术英语', '雅思']
const SEMESTER_PRESETS = ['2026-秋季', '2026-春季', '2027-春季', '2027-秋季']

/* ---------------- 请假 ---------------- */
export function LeavesPanel({ session }) {
  const isStudent = session.role === 'student'
  const canApprove = isStaff(session.role)
  const q = isStudent ? `?student_id=${session.userId}` : ''
  const { data, loading, error, reload } = useLoad(() => api('/api/student/leaves' + q), [q])
  const [form, setForm] = useState({ reason: '', start_time: '', end_time: '' })
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const rows = Array.isArray(data) ? data : []
  const list = canApprove ? rows.filter(x => x.status === '待审批') : rows

  const submit = async () => {
    if (!form.reason.trim() || busy) return
    setBusy(true); setMsg('')
    try {
      const body = { student_id: session.userId, reason: form.reason.trim() }
      if (form.start_time) body.start_time = form.start_time
      if (form.end_time) body.end_time = form.end_time
      await post('/api/student/leaves', body)
      setForm({ reason: '', start_time: '', end_time: '' })
      setMsg('已提交，等待老师审批')
      reload()
    } catch (e) {
      setMsg('提交失败：' + e.message)
    } finally { setBusy(false) }
  }

  const decide = async (id, ok) => {
    setBusy(true); setMsg('')
    try {
      await post(`/api/student/leaves/${id}/approve`, { approver_id: session.userId, approved: ok })
      setMsg(ok ? `已通过 #${id}` : `已驳回 #${id}`)
      reload()
    } catch (e) {
      setMsg('操作失败：' + e.message)
    } finally { setBusy(false) }
  }

  return (
    <div className="panel-body">
      <Notice text={msg} />
      {isStudent && (
        <div className="form-card">
          <h3>提交请假</h3>
          <Field label="请假事由（必填）">
            <input value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })}
              placeholder="例如：家中有事，需要请一天" />
          </Field>
          <div className="form-row">
            <Field label="开始时间"><input type="datetime-local" value={form.start_time}
              onChange={e => setForm({ ...form, start_time: e.target.value })} /></Field>
            <Field label="结束时间"><input type="datetime-local" value={form.end_time}
              onChange={e => setForm({ ...form, end_time: e.target.value })} /></Field>
          </div>
          <button className="sup-primary" onClick={submit} disabled={busy || !form.reason.trim()}>
            {busy ? '提交中…' : '提交申请'}
          </button>
        </div>
      )}

      <div className="panel-list">
        <h3>{canApprove ? '待审批' : isStudent ? '我的请假' : '全部请假'} <small>{list.length} 条</small></h3>
        <Loader loading={loading} error={error} />
        {!loading && !error && list.length === 0 && <Empty>{canApprove ? '没有待审批的请假' : '还没有记录'}</Empty>}
        {list.length > 0 && (
          <Table
            head={['学生', '事由', '时间', '状态', '审批人', canApprove ? '操作' : '提交时间']}
            rows={list.map(x => (
              <tr key={x.id}>
                <td>{x.student_name || x.student_id}</td>
                <td>{x.reason}</td>
                <td className="nowrap">{x.start_time || '—'}<br />{x.end_time || ''}</td>
                <td><Badge text={x.status} /></td>
                <td>{x.approver_name || '待分配'}</td>
                {canApprove ? (
                  <td className="sup-actions">
                    <button onClick={() => decide(x.id, true)} disabled={busy}>通过</button>
                    <button className="sup-danger" onClick={() => decide(x.id, false)} disabled={busy}>驳回</button>
                  </td>
                ) : (
                  <td className="nowrap">{x.create_time}</td>
                )}
              </tr>
            ))}
          />
        )}
      </div>
    </div>
  )
}

/* ---------------- 售后工单 ---------------- */
export function FeedbackPanel({ session }) {
  const isStudent = session.role === 'student'
  const canResolve = session.role !== 'student'
  const q = isStudent ? `?student_id=${session.userId}` : ''
  const { data, loading, error, reload } = useLoad(() => api('/api/student/feedback' + q), [q])
  const [draft, setDraft] = useState('')
  const [solving, setSolving] = useState(null)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const rows = Array.isArray(data) ? data : []
  const list = canResolve ? rows.filter(x => x.status === '待处理') : rows

  const create = async () => {
    if (!draft.trim() || busy) return
    setBusy(true); setMsg('')
    try {
      const d = await post('/api/student/feedback', { student_id: session.userId, content: draft.trim() })
      setDraft('')
      setMsg(`已提交工单 #${d.id}，状态「${d.status}」`)
      reload()
    } catch (e) {
      setMsg('提交失败：' + e.message)
    } finally { setBusy(false) }
  }

  const resolve = async id => {
    const text = (solving?.text || '').trim()
    if (!text || busy) return
    setBusy(true); setMsg('')
    try {
      await post(`/api/student/feedback/${id}/resolve`, { solution: text })
      setSolving(null)
      setMsg(`工单 #${id} 已回复，学生端可见`)
      reload()
    } catch (e) {
      setMsg('操作失败：' + e.message)
    } finally { setBusy(false) }
  }

  // 撤销工单：学生传了错的内容想删掉重新提交。已解决的工单后端会拒绝。
  const undo = async (id, content) => {
    if (busy) return
    if (!window.confirm(`确定撤销工单 #${id}（${content || '无内容'}）吗？撤销后可重新提交。`)) return
    setBusy(true); setMsg('')
    try {
      await del(`/api/student/feedback/${id}`)
      setMsg(`工单 #${id} 已撤销，可重新提交`)
      reload()
    } catch (e) {
      setMsg('撤销失败：' + e.message)
    } finally { setBusy(false) }
  }

  // 常见处理结果：点一下就填进输入框，最后仍可手动补一句
  const SOLUTION_PRESETS = [
    '已安排维修，明天上午上门',
    '已联系后勤，今天下午处理',
    '已退费，3 个工作日到账',
    '已电话沟通并致歉，学生认可',
    '已转交班主任跟进'
  ]

  return (
    <div className="panel-body">
      <Notice text={msg} />
      {isStudent && (
        <div className="form-card">
          <h3>提交报修 / 投诉</h3>
          <Field label="说清楚时间、地点、诉求">
            <textarea value={draft} onChange={e => setDraft(e.target.value)}
              placeholder="例如：宿舍空调从周一开始不制冷，已报修两次仍未处理。" />
          </Field>
          <button className="sup-primary" onClick={create} disabled={busy || !draft.trim()}>
            {busy ? '提交中…' : '提交工单'}
          </button>
        </div>
      )}

      <div className="panel-list">
        <h3>{canResolve ? '待处理工单' : '我的工单'} <small>{list.length} 条</small></h3>
        <Loader loading={loading} error={error} />
        {!loading && !error && list.length === 0 && <Empty>{canResolve ? '没有待处理的工单' : '还没有提交过'}</Empty>}
        {list.length > 0 && (
          <Table
            head={['学生', '内容', '状态', '处理结果', '操作']}
            rows={list.map(x => (
              <tr key={x.id}>
                <td>{x.student_name || x.student_id}</td>
                <td>{x.content}</td>
                <td><Badge text={x.status} /></td>
                <td>{x.solution || '等待处理'}</td>
                {canResolve ? (
                  <td className="sup-actions">
                    <button className={solving?.id === x.id ? 'on' : ''}
                      onClick={() => setSolving(solving?.id === x.id ? null : { id: x.id, text: '' })}>
                      {solving?.id === x.id ? '收起' : '处理'}
                    </button>
                  </td>
                ) : (
                  <td className="sup-actions">
                    <div className="nowrap" style={{ opacity: .6, fontSize: 11 }}>{x.create_time}</div>
                    {x.status !== '已解决' && (
                      <button onClick={() => undo(x.id, x.content)} disabled={busy}>撤销</button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          />
        )}

        {solving && (
          <div className="form-card solve-card">
            <h3>处理工单 #{solving.id}</h3>
            <div className="chip-row">
              {SOLUTION_PRESETS.map(t => (
                <button key={t} className={'chip' + (solving.text === t ? ' on' : '')}
                  onClick={() => setSolving({ id: solving.id, text: t })}>{t}</button>
              ))}
            </div>
            <Field label="处理结果（学生端可见）" hint="点上面的常用说法直接填入，也可以再补充细节">
              <textarea value={solving.text}
                onChange={e => setSolving({ id: solving.id, text: e.target.value })}
                placeholder="选择上面的常用说法，或直接写处理结果" />
            </Field>
            <div className="btn-row">
              <button className="sup-primary" onClick={() => resolve(solving.id)}
                disabled={busy || !solving.text.trim()}>
                {busy ? '提交中…' : '提交并通知学生'}
              </button>
              <button className="btn-ghost" onClick={() => setSolving(null)}>取消</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ---------------- 成绩 ---------------- */
export function ScoresPanel({ session }) {
  const isStudent = session.role === 'student'
  const canRecord = isStaff(session.role)
  const q = isStudent ? `?student_id=${session.userId}` : ''
  const { data, loading, error, reload } = useLoad(() => api('/api/student/scores' + q), [q])
  const { data: students } = useLoad(
    () => (canRecord ? api('/api/identity/students') : Promise.resolve([])), [canRecord]
  )
  const [form, setForm] = useState({ student_id: '', course_name: '', score: 85, semester: SEMESTER_PRESETS[0] })
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  // 正在编辑的成绩行：保存要改的字段（只传改过的，后端 PATCH 只更新传了的）
  const [editing, setEditing] = useState(null)

  const rows = Array.isArray(data) ? data : []
  const list = Array.isArray(students) ? students : []

  // 课程候选 = 历史成绩里出现过的课程 + 常用课程，去重后给下拉用
  const courseOptions = Array.from(new Set([
    ...rows.map(r => r.course_name).filter(Boolean),
    ...COURSE_PRESETS
  ]))

  const record = async () => {
    if (!form.student_id || !form.course_name || busy) return
    setBusy(true); setMsg('')
    try {
      await post('/api/student/scores', {
        student_id: Number(form.student_id),
        course_name: form.course_name,
        score: Number(form.score),
        semester: form.semester || null
      })
      setForm({ student_id: '', course_name: '', score: 85, semester: SEMESTER_PRESETS[0] })
      setMsg('成绩已录入')
      reload()
    } catch (e) {
      setMsg('录入失败：' + e.message)
    } finally { setBusy(false) }
  }

  // 保存编辑：只提交改过的字段；student_id 不可改（后端也不允许）
  const saveEdit = async id => {
    if (!editing || busy) return
    setBusy(true); setMsg('')
    try {
      await patch(`/api/student/scores/${id}`, {
        course_name: editing.course_name,
        score: Number(editing.score),
        semester: editing.semester || null
      })
      setEditing(null)
      setMsg(`成绩 #${id} 已修改`)
      reload()
    } catch (e) {
      setMsg('修改失败：' + e.message)
    } finally { setBusy(false) }
  }

  const remove = async id => {
    if (busy) return
    setBusy(true); setMsg('')
    try {
      await del(`/api/student/scores/${id}`)
      setMsg(`成绩 #${id} 已删除`)
      reload()
    } catch (e) {
      setMsg('删除失败：' + e.message)
    } finally { setBusy(false) }
  }

  return (
    <div className="panel-body">
      <Notice text={msg} />
      {canRecord && (
        <div className="form-card">
          <h3>录入成绩</h3>
          <div className="form-row">
            <Field label="学生">
              <select value={form.student_id} onChange={e => setForm({ ...form, student_id: e.target.value })}>
                <option value="">请选择</option>
                {list.map(u => <option key={u.id} value={u.id}>{u.real_name}（{u.username}）</option>)}
              </select>
            </Field>
            <Field label="课程">
              <select value={form.course_name} onChange={e => setForm({ ...form, course_name: e.target.value })}>
                <option value="">请选择</option>
                {courseOptions.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </Field>
            <Field label={`分数 ${form.score}`}>
              <input type="range" min="0" max="100" step="1" value={form.score}
                className="score-range"
                onChange={e => setForm({ ...form, score: Number(e.target.value) })} />
              <div className="range-ticks"><span>0</span><span>60 及格</span><span>100</span></div>
            </Field>
            <Field label="学期">
              <select value={form.semester} onChange={e => setForm({ ...form, semester: e.target.value })}>
                {SEMESTER_PRESETS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
          </div>
          <button className="sup-primary" onClick={record}
            disabled={busy || !form.student_id || !form.course_name}>
            {busy ? '录入中…' : `保存成绩${form.student_id && form.course_name ? `：${form.course_name} ${form.score} 分` : ''}`}
          </button>
        </div>
      )}

      <div className="panel-list">
        <h3>{isStudent ? '我的成绩' : '全部学生成绩'} <small>{rows.length} 条</small></h3>
        <Loader loading={loading} error={error} />
        {!loading && !error && rows.length === 0 && <Empty />}
        {rows.length > 0 && (
          <Table
            head={['学生', '课程', '分数', '学期', '录入时间', ...(canRecord ? ['操作'] : [])]}
            rows={rows.map(x => (
              editing?.id === x.id ? (
                <tr key={x.id}>
                  <td>{x.student_name || x.student_id}</td>
                  <td>
                    <select value={editing.course_name}
                      onChange={e => setEditing({ ...editing, course_name: e.target.value })}>
                      {courseOptions.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </td>
                  <td>
                    <input type="number" min="0" max="100" value={editing.score}
                      onChange={e => setEditing({ ...editing, score: e.target.value })} />
                  </td>
                  <td>
                    <select value={editing.semester || ''}
                      onChange={e => setEditing({ ...editing, semester: e.target.value })}>
                      {SEMESTER_PRESETS.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="nowrap">{x.create_time}</td>
                  <td className="sup-actions">
                    <button onClick={() => saveEdit(x.id)} disabled={busy}>保存</button>
                    <button className="btn-ghost" onClick={() => setEditing(null)} disabled={busy}>取消</button>
                  </td>
                </tr>
              ) : (
                <tr key={x.id}>
                  <td>{x.student_name || x.student_id}</td>
                  <td>{x.course_name}</td>
                  <td><b>{x.score}</b></td>
                  <td>{x.semester || '—'}</td>
                  <td className="nowrap">{x.create_time}</td>
                  {canRecord && (
                    <td className="sup-actions">
                      <button onClick={() => setEditing({
                        id: x.id, course_name: x.course_name, score: x.score, semester: x.semester || ''
                      })} disabled={busy}>编辑</button>
                      <button className="sup-danger" onClick={() => remove(x.id)} disabled={busy}>删除</button>
                    </td>
                  )}
                </tr>
              )
            ))}
          />
        )}
      </div>
    </div>
  )
}

/**
 * 心理画像：按时间倒序列出，每条只保留「时间 + 状态（分数）」
 * 学生端和员工端共用，避免一处改了另一处还是 JSON。
 */
function PsyHistory({ profile }) {
  const days = groupByDay(profile?.emotion_history)
  if (!days.length) return <Empty>还没有情绪记录</Empty>
  return (
    <div className="psy-days">
      <div className="psy-latest">
        <span>最近一次</span>
        <b className={'psy-tag ' + tagClass(profile.latest_emotion_tag)}>{profile.latest_emotion_tag || '—'}</b>
        <span>{profile.emotion_score ?? '—'} 分</span>
        <small>{profile.last_interaction_time || ''}</small>
      </div>
      {days.map(day => (
        <div className="psy-day" key={day.date}>
          <span className="psy-date">{day.date}</span>
          <div className="psy-slots">
            {day.items.map((x, i) => (
              <span className="psy-slot" key={i}>
                <small>{(x.time || '').slice(11, 16)}</small>
                <b className={'psy-tag ' + tagClass(x.tag)}>{x.tag || '—'}</b>
                <span>{x.score ?? '—'} 分</span>
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * 对话记录查询：只写不查的缺口补齐。
 * 学生传自己的 userId（后端强制只看自己）；员工传选中的学生 id。
 */
function ConversationList({ userId, title = '对话记录' }) {
  const { data, loading, error, reload } = useLoad(
    () => (userId ? api(`/api/psych/conversations?user_id=${userId}&limit=50`) : Promise.resolve([])),
    [userId]
  )
  const rows = Array.isArray(data) ? data : []
  return (
    <div className="panel-list">
      <h3>{title} <small>{rows.length} 条</small></h3>
      <Loader loading={loading} error={error} />
      {!userId && <p className="hint-text">选择学生后显示其在各智能体的历史对话。</p>}
      {userId && !loading && !error && rows.length === 0 && <Empty>还没有对话记录</Empty>}
      {rows.length > 0 && (
        <Table
          head={['时间', '智能体', '我的输入', 'AI 回复', '情绪']}
          rows={rows.map(x => (
            <tr key={x.id}>
              <td className="nowrap">{(x.create_time || '').slice(5, 16)}</td>
              <td>{x.agent_type}</td>
              <td>{x.user_input}</td>
              <td>{x.ai_output || '—'}</td>
              <td><Badge text={x.emotion_tag || '—'} /></td>
            </tr>
          ))}
        />
      )}
    </div>
  )
}

/* ---------------- 心理 ---------------- */
export function PsychPanel({ session }) {
  const isStudent = session.role === 'student'
  const canUpdate = isStaff(session.role)
  const [text, setText] = useState('')
  const [result, setResult] = useState(null)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const alerts = useLoad(() => (isStudent ? Promise.resolve([]) : api('/api/psych/alerts')), [isStudent])
  const myProfile = useLoad(
    () => (isStudent ? api(`/api/psych/profile/${session.userId}`) : Promise.resolve(null)), [isStudent, session.userId]
  )
  // 员工端：学生下拉 + 员工（老师）下拉，全部点选，不手打 ID
  const students = useLoad(
    () => (canUpdate ? api('/api/identity/students') : Promise.resolve([])), [canUpdate]
  )
  const employees = useLoad(
    () => (canUpdate ? api('/api/identity/employees') : Promise.resolve([])), [canUpdate]
  )
  const [viewId, setViewId] = useState('')
  const otherProfile = useLoad(
    () => (viewId ? api(`/api/psych/profile/${viewId}`) : Promise.resolve(null)), [viewId]
  )

  const studentList = Array.isArray(students.data) ? students.data : []
  const staffList = Array.isArray(employees.data) ? employees.data : []
  // 管理员不参与心理跟进指派（系统管理账号不出现在候选里）
  const assignable = staffList.filter(u => u.employee_role !== '管理员')
  const meAssignable = session.employeeRole !== '管理员'

  const assess = async () => {
    if (!text.trim() || busy) return
    setBusy(true); setMsg('')
    try {
      const d = await post('/api/psych/assess', { student_id: session.userId, text: text.trim() })
      setResult(d)
      setText('')
      myProfile.reload()
    } catch (e) {
      setMsg('提交失败：' + e.message)
    } finally { setBusy(false) }
  }

  /**
   * 更新预警：状态只允许「未处理 / 跟进中 / 已解除」（后端枚举）。
   * teacher_id 不给就由当前登录者跟进——「现在是陈老师登录，就记陈老师」。
   */
  const mark = async (alert, status, teacherId) => {
    setBusy(true); setMsg('')
    try {
      await patch(`/api/psych/alerts/${alert.id}`, {
        status,
        teacher_id: Number(teacherId || alert.teacher_id || session.userId)
      })
      setMsg(`预警 #${alert.id} 已更新为「${status}」`)
      alerts.reload()
    } catch (e) {
      setMsg('更新失败：' + e.message)
    } finally { setBusy(false) }
  }

  if (isStudent) {
    return (
      <div className="panel-body">
        <Notice text={msg} />
        <div className="form-card">
          <h3>记录今天的状态</h3>
          <Field label="用一两句话说说最近的感受" hint="内容只用于生成关怀建议，老师看到的只有预警级别">
            <textarea value={text} onChange={e => setText(e.target.value)}
              placeholder="例如：最近作业很多，晚上睡不好，有点焦虑。" />
          </Field>
          <button className="sup-primary" onClick={assess} disabled={busy || !text.trim()}>
            {busy ? '分析中…' : '提交并获取建议'}
          </button>
        </div>
        {result && (
          <div className="form-card">
            <h3>评估结果</h3>
            <div className="psy-result">
              <div className="psy-top">
                <span className={'psy-tag ' + tagClass(result.emotion_tag)}>{result.emotion_tag || '—'}</span>
                <b className="psy-score">{result.emotion_score ?? '—'}<small> / 100</small></b>
                <span className={'psy-risk ' + riskClass(result.risk_level)}>风险 {result.risk_level || '—'}</span>
              </div>
              <p className="psy-msg">{result.message || '已记录今天的情绪'}</p>
              {result.alerted && <div className="psy-alert">已触发预警，班主任会收到提醒并跟进</div>}
            </div>
          </div>
        )}
        <div className="panel-list">
          <h3>我的心理状态 <small>按天汇总</small></h3>
          {myProfile.loading && <div className="sup-empty">读取中…</div>}
          {!myProfile.loading && !myProfile.data && <Empty>还没有记录</Empty>}
          {myProfile.data && <PsyHistory profile={myProfile.data} />}
        </div>
        <ConversationList userId={session.userId} title="我的对话记录" />
      </div>
    )
  }

  const list = Array.isArray(alerts.data) ? alerts.data : []
  return (
    <div className="panel-body">
      <Notice text={msg} />
      <div className="panel-list">
        <h3>心理预警 <small>{list.length} 条</small></h3>
        <Loader loading={alerts.loading} error={alerts.error} />
        {!alerts.loading && !alerts.error && list.length === 0 && <Empty />}
        {list.length > 0 && (
          <Table
            head={['学生', '触发原因', '风险等级', '状态', '跟进老师', canUpdate ? '操作' : '时间']}
            rows={list.map(x => (
              <tr key={x.id}>
                <td>{x.student_name || x.student_id}</td>
                <td>{x.trigger_reason}</td>
                <td><Badge text={x.risk_level} /></td>
                <td><Badge text={x.status} /></td>
                <td>
                  {canUpdate ? (
                    <select className="cell-select" value={x.teacher_id || ''}
                      onChange={e => mark(x, x.status === '已解除' ? '已解除' : (x.status || '未处理'), e.target.value)}>
                      <option value="">未指派</option>
                      {assignable.map(u => <option key={u.id} value={u.id}>{u.real_name}</option>)}
                    </select>
                  ) : (x.teacher_name || '—')}
                </td>
                {canUpdate ? (
                  <td className="sup-actions">
                    <button onClick={() => mark(x, '跟进中', meAssignable ? session.userId : x.teacher_id)}
                      disabled={busy || x.status === '跟进中' || (!meAssignable && !x.teacher_id)}>
                      由我跟进
                    </button>
                    <button className="btn-ghost" onClick={() => mark(x, '已解除')}
                      disabled={busy || x.status === '已解除'}>解除</button>
                  </td>
                ) : <td className="nowrap">{x.create_time}</td>}
              </tr>
            ))}
          />
        )}
        <p className="hint-text">
          「由我跟进」会把当前登录的 {session.realName} 记为跟进老师；也可以在「跟进老师」列直接指派。
          {!meAssignable && '（管理员账号不参与指派，请先在列里选一位老师）'}
        </p>
      </div>
      <div className="form-card">
        <h3>查看学生心理画像</h3>
        <Field label="选择学生">
          <select value={viewId} onChange={e => setViewId(e.target.value)}>
            <option value="">请选择学生</option>
            {studentList.map(u => (
              <option key={u.id} value={u.id}>{u.real_name}（{u.username}）</option>
            ))}
          </select>
        </Field>
        {otherProfile.loading && <div className="sup-empty">读取中…</div>}
        {otherProfile.data && <PsyHistory profile={otherProfile.data} />}
        {!viewId && <p className="hint-text">选择学生后按时间倒序显示每次记录的状态与分数。</p>}
      </div>
      <ConversationList userId={viewId} title="该学生的对话记录" />
    </div>
  )
}

/* ---------------- 意向客户 ---------------- */
export function LeadsPanel({ session }) {
  const canCreate = session.role === 'employee' || session.role === 'admin'
  const { data, loading, error, reload } = useLoad(() => api('/api/employee/leads'), [])
  const projects = useLoad(() => api('/api/catalog/projects'), [])
  const [form, setForm] = useState({ customer_name: '', contact_info: '', background_info: '' })
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  // 正在签约的线索：{ lead, project_id, username }
  const [signing, setSigning] = useState(null)
  // 正在编辑资料的线索：只存要改的字段；编辑和签约互斥，同一时刻只开一个
  const [editing, setEditing] = useState(null)
  const signRef = useRef(null)

  // 表格很长，点「签约」后把表单滚进视野，省得用户自己找
  useEffect(() => {
    if (signing && signRef.current) signRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [signing])

  const rows = Array.isArray(data) ? data : []
  const projectList = Array.isArray(projects.data) ? projects.data : []
  // 与后端 schemas.LeadStatus 保持一致（原来的「已成交」后端不认）
  const STATUS = ['新增意向', '跟进中', '已签约', '已流失']

  const create = async () => {
    if (!form.customer_name.trim() || busy) return
    setBusy(true); setMsg('')
    try {
      await post('/api/employee/leads', {
        customer_name: form.customer_name.trim(),
        contact_info: form.contact_info.trim(),
        background_info: form.background_info.trim(),
        follow_up_history: '网页录入',
        owner_employee_id: session.userId
      })
      setForm({ customer_name: '', contact_info: '', background_info: '' })
      setMsg('客户已录入（此时还没有账号，签约后才会创建）')
      reload()
    } catch (e) {
      setMsg('录入失败：' + e.message)
    } finally { setBusy(false) }
  }

  const move = async (id, status) => {
    setBusy(true); setMsg('')
    try {
      await patch(`/api/employee/leads/${id}/status`, { status })
      setMsg(`客户 #${id} 状态改为「${status}」`)
      reload()
    } catch (e) {
      setMsg('更新失败：' + e.message)
    } finally { setBusy(false) }
  }

  // 编辑客户资料：只提交改过的字段；状态和负责人不在编辑范围（走各自的接口）
  const saveEdit = async id => {
    if (!editing || busy) return
    setBusy(true); setMsg('')
    try {
      await patch(`/api/employee/leads/${id}`, {
        customer_name: editing.customer_name,
        contact_info: editing.contact_info,
        background_info: editing.background_info
      })
      setEditing(null)
      setMsg(`客户 #${id} 资料已修改`)
      reload()
    } catch (e) {
      setMsg('修改失败：' + e.message)
    } finally { setBusy(false) }
  }

  // 删除客户：已签约的后端会拒绝（409），这里先做一次前端确认，防误触
  const remove = async lead => {
    if (busy || !window.confirm(`确定删除客户「${lead.customer_name}」吗？此操作不可撤销。`)) return
    setBusy(true); setMsg('')
    try {
      await del(`/api/employee/leads/${lead.id}`)
      setMsg(`客户「${lead.customer_name}」已删除`)
      reload()
    } catch (e) {
      // 后端已签约返回 409，给出可操作的提示（引导改为已流失）
      setMsg(/签约/.test(e.message) ? e.message : '删除失败：' + e.message)
    } finally { setBusy(false) }
  }

  /** 签约：标记已签约 + 创建学生账号（若没有）+ 把课程写进学生系统 */
  const doSign = async () => {
    if (!signing?.project_id || busy) return
    setBusy(true); setMsg('')
    try {
      const d = await post(`/api/employee/leads/${signing.lead.id}/sign`, {
        project_id: Number(signing.project_id),
        username: (signing.username || '').trim() || null
      })
      setSigning(null)
      setMsg(d.message)
      reload()
    } catch (e) {
      setMsg('签约失败：' + e.message)
    } finally { setBusy(false) }
  }

  return (
    <div className="panel-body">
      <Notice text={msg} />
      {canCreate && (
        <div className="form-card">
          <h3>录入意向客户</h3>
          <div className="form-row">
            <Field label="客户姓名"><input value={form.customer_name}
              onChange={e => setForm({ ...form, customer_name: e.target.value })} placeholder="如 王女士" /></Field>
            <Field label="联系方式"><input value={form.contact_info}
              onChange={e => setForm({ ...form, contact_info: e.target.value })} placeholder="手机号 / 微信" /></Field>
          </div>
          <Field label="背景信息">
            <textarea value={form.background_info}
              onChange={e => setForm({ ...form, background_info: e.target.value })}
              placeholder="如：孩子高三，想去新加坡读本科，预算 20 万/年" />
          </Field>
          <button className="sup-primary" onClick={create} disabled={busy || !form.customer_name.trim()}>
            {busy ? '保存中…' : '保存客户'}
          </button>
        </div>
      )}

      <div className="panel-list">
        <h3>客户列表 <small>{rows.length} 条</small></h3>
        <p className="hint-text">未签约的客户只是线索，不会出现在学生系统里；签约并选定课程后，才会自动创建学生账号并开通课程。</p>
        <Loader loading={loading} error={error} />
        {!loading && !error && rows.length === 0 && <Empty />}
        {rows.length > 0 && (
          <Table
            head={['客户', '联系方式', '背景', '状态', '推进', '签约', '编辑']}
            rows={rows.map(x => (
              editing?.id === x.id ? (
                <tr key={x.id}>
                  <td><input value={editing.customer_name}
                    onChange={e => setEditing({ ...editing, customer_name: e.target.value })} /></td>
                  <td><input value={editing.contact_info || ''}
                    onChange={e => setEditing({ ...editing, contact_info: e.target.value })} /></td>
                  <td><input value={editing.background_info || ''}
                    onChange={e => setEditing({ ...editing, background_info: e.target.value })} /></td>
                  <td><Badge text={x.status} /></td>
                  <td colSpan="2" className="hint-text">修改资料时暂停状态 / 签约操作</td>
                  <td className="sup-actions">
                    <button onClick={() => saveEdit(x.id)} disabled={busy || !editing.customer_name.trim()}>保存</button>
                    <button className="btn-ghost" onClick={() => setEditing(null)} disabled={busy}>取消</button>
                  </td>
                </tr>
              ) : (
                <tr key={x.id}>
                  <td>{x.customer_name}</td>
                  <td>{x.contact_info || '—'}</td>
                  <td>{x.background_info || '—'}</td>
                  <td><Badge text={x.status} /></td>
                  <td className="sup-actions">
                    <select value={x.status} onChange={e => move(x.id, e.target.value)} disabled={busy}>
                      {STATUS.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="sup-actions">
                    <button className={signing?.lead.id === x.id ? 'on' : ''}
                      onClick={() => {
                        setEditing(null)
                        setSigning(signing?.lead.id === x.id ? null : {
                          lead: x, project_id: projectList[0]?.id || '', username: `student_${x.id}`
                        })
                      }}>
                      {signing?.lead.id === x.id ? '收起' : (x.status === '已签约' ? '追加课程' : '签约')}
                    </button>
                  </td>
                  <td className="sup-actions">
                    <button onClick={() => { setSigning(null); setEditing({
                      id: x.id, customer_name: x.customer_name,
                      contact_info: x.contact_info || '', background_info: x.background_info || ''
                    }) }} disabled={busy}>编辑</button>
                    <button className="sup-danger" onClick={() => remove(x)} disabled={busy}>删除</button>
                  </td>
                </tr>
              )
            ))}
          />
        )}

        {signing && (
          <div className="form-card solve-card" ref={signRef}>
            <h3>签约 · {signing.lead.customer_name}</h3>
            <div className="form-row">
              <Field label="报读课程" hint="签约必须选一门课，会写进学生个人系统">
                <select value={signing.project_id}
                  onChange={e => setSigning({ ...signing, project_id: e.target.value })}>
                  {projectList.map(p => (
                    <option key={p.id} value={p.id}>{p.project_name}</option>
                  ))}
                </select>
              </Field>
              <Field label="学生登录账号" hint="留空自动生成；重名会自动加序号">
                <input value={signing.username}
                  onChange={e => setSigning({ ...signing, username: e.target.value })} />
              </Field>
            </div>
            <p className="hint-text">
              提交后会：① 客户状态改为「已签约」；② 若该姓名还没有学生账号，自动创建（初始口令 123456）；③ 把「{projectList.find(p => String(p.id) === String(signing.project_id))?.project_name || '所选课程'}」开通到他的个人系统。
            </p>
            <div className="btn-row">
              <button className="sup-primary" onClick={doSign} disabled={busy || !signing.project_id}>
                {busy ? '提交中…' : '确认签约并开通课程'}
              </button>
              <button className="btn-ghost" onClick={() => setSigning(null)}>取消</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ---------------- 员工日报 ---------------- */
export function ReportsPanel({ session }) {
  const { data, loading, error, reload } = useLoad(() => api('/api/employee/reports'), [])
  const [content, setContent] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  // 正在编辑的日报：{ id, content, report_date }
  const [editing, setEditing] = useState(null)
  const rows = Array.isArray(data) ? data : []

  const submit = async () => {
    if (!content.trim() || busy) return
    setBusy(true); setMsg('')
    try {
      await post('/api/employee/reports', { employee_id: session.userId, content: content.trim(), report_date: today() })
      setContent('')
      setMsg('日报已提交')
      reload()
    } catch (e) {
      setMsg('提交失败：' + e.message)
    } finally { setBusy(false) }
  }

  const saveEdit = async id => {
    if (!editing || busy) return
    setBusy(true); setMsg('')
    try {
      await patch(`/api/employee/reports/${id}`, { content: editing.content, report_date: editing.report_date })
      setEditing(null)
      setMsg(`日报 #${id} 已修改`)
      reload()
    } catch (e) {
      setMsg('修改失败：' + e.message)
    } finally { setBusy(false) }
  }

  const remove = async id => {
    if (busy || !window.confirm(`确定删除日报 #${id} 吗？此操作不可撤销。`)) return
    setBusy(true); setMsg('')
    try {
      await del(`/api/employee/reports/${id}`)
      setMsg(`日报 #${id} 已删除`)
      reload()
    } catch (e) {
      setMsg('删除失败：' + e.message)
    } finally { setBusy(false) }
  }

  return (
    <div className="panel-body">
      <Notice text={msg} />
      <div className="form-card">
        <h3>写今天的日报</h3>
        <Field label="今天做了什么、遇到什么问题">
          <textarea value={content} onChange={e => setContent(e.target.value)}
            placeholder="例如：跟进 3 位意向客户，2 位约了到校参观。" />
        </Field>
        <button className="sup-primary" onClick={submit} disabled={busy || !content.trim()}>
          {busy ? '提交中…' : '提交日报'}
        </button>
      </div>
      <div className="panel-list">
        <h3>日报记录 <small>{rows.length} 条</small></h3>
        <Loader loading={loading} error={error} />
        {!loading && !error && rows.length === 0 && <Empty />}
        {rows.length > 0 && (
          <Table
            head={['员工', '日期', '内容', '提交时间', '操作']}
            rows={rows.map(x => (
              editing?.id === x.id ? (
                <tr key={x.id}>
                  <td>{x.employee_name || x.employee_id}</td>
                  <td><input type="date" value={editing.report_date}
                    onChange={e => setEditing({ ...editing, report_date: e.target.value })} /></td>
                  <td><textarea value={editing.content}
                    onChange={e => setEditing({ ...editing, content: e.target.value })} /></td>
                  <td className="nowrap">{x.create_time}</td>
                  <td className="sup-actions">
                    <button onClick={() => saveEdit(x.id)} disabled={busy || !editing.content.trim()}>保存</button>
                    <button className="btn-ghost" onClick={() => setEditing(null)} disabled={busy}>取消</button>
                  </td>
                </tr>
              ) : (
                <tr key={x.id}>
                  <td>{x.employee_name || x.employee_id}</td>
                  <td className="nowrap">{x.report_date}</td>
                  <td>{x.content}</td>
                  <td className="nowrap">{x.create_time}</td>
                  <td className="sup-actions">
                    <button onClick={() => setEditing({
                      id: x.id, content: x.content, report_date: x.report_date
                    })} disabled={busy}>编辑</button>
                    <button className="sup-danger" onClick={() => remove(x.id)} disabled={busy}>删除</button>
                  </td>
                </tr>
              )
            ))}
          />
        )}
      </div>
    </div>
  )
}

/* ---------------- 活动 ---------------- */
export function EventsPanel({ session }) {
  const { data, loading, error, reload } = useLoad(() => api('/api/catalog/events'), [])
  const canSeeRegs = ['employee', 'teacher', 'admin'].includes(session.role)
  // 学生只查自己的报名（后端强制按 token 过滤）；员工查全量
  const regs = useLoad(
    () => api(canSeeRegs ? '/api/catalog/registrations' : '/api/catalog/my-registrations'),
    [canSeeRegs]
  )
  // 报名表只存 customer_id，姓名在前端用线索接口补（后端课程模块不再反向依赖员工模块）
  const leads = useLoad(() => (canSeeRegs ? api('/api/employee/leads') : Promise.resolve([])), [canSeeRegs])
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const rows = Array.isArray(data) ? data : []
  const regList = Array.isArray(regs.data) ? regs.data : []
  const leadMap = new Map((Array.isArray(leads.data) ? leads.data : []).map(l => [l.id, l]))

  // ===== 新增活动（仅员工/管理员；学生看不到入口）=====
  const [creating, setCreating] = useState(false)
  const blankEvent = { event_name: '', event_type: '线下', start_time: '', location: '', max_participants: '' }
  const [form, setForm] = useState(blankEvent)
  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const createEvent = async e => {
    e.preventDefault()
    if (busy) return
    if (!form.event_name.trim() || !form.start_time.trim()) {
      setMsg('请填写活动名称和开始时间'); return
    }
    setBusy(true); setMsg('')
    try {
      const body = {
        event_name: form.event_name.trim(),
        event_type: form.event_type,
        start_time: form.start_time.trim(),
        location: form.location.trim() || null,
        max_participants: form.max_participants === '' ? null : Number(form.max_participants),
      }
      await post('/api/catalog/events', body)
      setMsg(`活动「${body.event_name}」已创建`)
      setForm(blankEvent); setCreating(false)
      reload()
    } catch (err) {
      setMsg('创建失败：' + err.message)
    } finally { setBusy(false) }
  }

  // 我（当前登录者）的有效报名：event_id -> 报名记录 id，供学生本人取消用
  const myRegByEvent = new Map(
    regList
      .filter(r => String(r.customer_id) === String(session.userId) && r.status !== '已取消')
      .map(r => [Number(r.event_id), r.id])
  )
  const myEventIds = new Set(myRegByEvent.keys())

  const join = async id => {
    setBusy(true); setMsg('')
    try {
      await post(`/api/catalog/events/${id}/register`, { customer_id: session.userId })
      setMsg('报名成功，活动开始前会收到提醒')
      reload()
      regs.reload()
    } catch (e) {
      const dup = /已报名/.test(e.message)
      setMsg(dup ? '你已经报过这个活动了' : '报名失败：' + e.message)
      regs.reload()
    } finally { setBusy(false) }
  }

  // 取消报名：软删除（状态改「已取消」+ 活动人数 -1），后端已防重复取消
  const cancelReg = async regId => {
    if (busy || !window.confirm(`确定取消这条报名（#${regId}）吗？名额会释放给别人。`)) return
    setBusy(true); setMsg('')
    try {
      await post(`/api/catalog/registrations/${regId}/cancel`)
      setMsg(`报名 #${regId} 已取消，名额已释放`)
      reload()
      regs.reload()
    } catch (e) {
      setMsg('取消失败：' + e.message)
      regs.reload()
    } finally { setBusy(false) }
  }

  return (
    <div className="panel-body">
      <Notice text={msg} />

      {/* 新增活动入口：只给员工/管理员 */}
      {canSeeRegs && (
        <div className="create-wrap">
          <button className="sup-primary" onClick={() => setCreating(v => !v)} disabled={busy}>
            {creating ? '收起表单' : '＋ 新增活动'}
          </button>
          {creating && (
            <form className="form-card create-form" onSubmit={createEvent}>
              <div className="form-grid">
                <Field label="活动名称"><input value={form.event_name}
                  onChange={e => setF('event_name', e.target.value)} placeholder="如：2026 冬季开放日" /></Field>
                <Field label="类型">
                  <select value={form.event_type} onChange={e => setF('event_type', e.target.value)}>
                    <option value="线下">线下</option>
                    <option value="线上">线上</option>
                  </select>
                </Field>
                <Field label="开始时间" hint="格式：2026-12-01 14:00">
                  <input type="datetime-local" value={form.start_time}
                    onChange={e => setF('start_time', e.target.value)} />
                </Field>
                <Field label="地点 / 链接"><input value={form.location}
                  onChange={e => setF('location', e.target.value)} placeholder="如：广州天河校区" /></Field>
                <Field label="人数上限"><input type="number" min="1" value={form.max_participants}
                  onChange={e => setF('max_participants', e.target.value)} placeholder="如：50" /></Field>
              </div>
              <div className="btn-row">
                <button className="sup-primary" type="submit" disabled={busy}>{busy ? '提交中…' : '创建活动'}</button>
                <button className="btn-ghost" type="button" onClick={() => setCreating(false)}>取消</button>
              </div>
            </form>
          )}
        </div>
      )}

      <div className="event-grid">
        {rows.map(e => {
          const joined = myEventIds.has(Number(e.id))
          const full = e.current_participants >= e.max_participants
          return (
            <article className={'soft-card' + (joined ? ' is-joined' : '')} key={e.id}>
              <span className="tag">{e.event_type}</span>
              <h3>{e.event_name}</h3>
              <p>{e.start_time} · {e.location}</p>
              <small>已报名 {e.current_participants} / {e.max_participants}</small>
              <div className="card-foot">
                {session.role === 'student' && (
                  joined
                    ? <button className="enrolled-badge" title="点击取消报名"
                        onClick={() => cancelReg(myRegByEvent.get(Number(e.id)))} disabled={busy}>✓ 已报名 · 取消</button>
                    : full
                      ? <span className="hint-text">名额已满</span>
                      : <button className="sup-primary" onClick={() => join(e.id)} disabled={busy}>报名</button>
                )}
                {canSeeRegs && joined && <span className="hint-text">你已报名</span>}
              </div>
            </article>
          )
        })}
        {!loading && !error && rows.length === 0 && <Empty>暂无活动</Empty>}
      </div>

      {canSeeRegs && (
        <div className="panel-list">
          <h3>报名记录 <small>{regList.length} 条</small></h3>
          <Loader loading={regs.loading} error={regs.error} />
          {regList.length > 0 && (
            <Table
              head={['活动', '报名人', '联系方式', '状态', '时间', '操作']}
              rows={regList.map(r => (
                <tr key={r.id}>
                  <td>{r.event_name || r.event_id}</td>
                  <td>{leadMap.get(r.customer_id)?.customer_name || `客户 #${r.customer_id}`}</td>
                  <td>{leadMap.get(r.customer_id)?.contact_info || '—'}</td>
                  <td><Badge text={r.status} /></td>
                  <td className="nowrap">{r.create_time}</td>
                  <td className="sup-actions">
                    {r.status !== '已取消' ? (
                      <button className="sup-danger" onClick={() => cancelReg(r.id)} disabled={busy}>取消</button>
                    ) : <span className="hint-text">—</span>}
                  </td>
                </tr>
              ))}
            />
          )}
        </div>
      )}
    </div>
  )
}

/* ---------------- 项目 ---------------- */
export function ProjectsPanel({ session, onGo }) {
  const { data, loading, error, reload } = useLoad(() => api('/api/catalog/projects'), [])
  const isStudent = session.role === 'student'
  const canManage = ['employee', 'teacher', 'admin'].includes(session.role)
  const mine = useLoad(
    () => (isStudent ? api(`/api/student/enrollments?student_id=${session.userId}`) : Promise.resolve(null)),
    [isStudent, session.userId]
  )

  // ===== 新增项目（仅员工/管理员；学生看不到入口）=====
  const [creating, setCreating] = useState(false)
  const blank = { project_name: '', category: '', description: '', target_audience: '' }
  const [form, setForm] = useState(blank)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const createProject = async e => {
    e.preventDefault()
    if (busy) return
    if (!form.project_name.trim()) { setMsg('请填写项目名称'); return }
    setBusy(true); setMsg('')
    try {
      await post('/api/catalog/projects', {
        project_name: form.project_name.trim(),
        category: form.category.trim() || null,
        description: form.description.trim() || null,
        target_audience: form.target_audience.trim() || null,
      })
      setMsg(`项目「${form.project_name.trim()}」已创建`)
      setForm(blank); setCreating(false)
      reload()
    } catch (err) {
      setMsg('创建失败：' + err.message)
    } finally { setBusy(false) }
  }

  const rows = Array.isArray(data) ? data : []
  const enrolled = mine.data?.items || []
  const enrolledIds = new Set(enrolled.map(x => x.project_id))
  const signed = !!mine.data?.signed
  const list = signed ? rows.filter(p => !enrolledIds.has(p.id)) : rows

  return (
    <div className="panel-body">
      <Notice text={msg} />

      {/* 新增项目入口：只给员工/管理员 */}
      {canManage && (
        <div className="create-wrap">
          <button className="sup-primary" onClick={() => setCreating(v => !v)} disabled={busy}>
            {creating ? '收起表单' : '＋ 新增项目'}
          </button>
          {creating && (
            <form className="form-card create-form" onSubmit={createProject}>
              <div className="form-grid">
                <Field label="项目名称"><input value={form.project_name}
                  onChange={e => setF('project_name', e.target.value)} placeholder="如：德国双元制项目" /></Field>
                <Field label="类别"><input value={form.category}
                  onChange={e => setF('category', e.target.value)} placeholder="如：国际本科 / 德国项目" /></Field>
                <Field label="适合人群"><input value={form.target_audience}
                  onChange={e => setF('target_audience', e.target.value)} placeholder="如：高中毕业生" /></Field>
                <Field label="项目介绍">
                  <textarea rows="2" value={form.description}
                    onChange={e => setF('description', e.target.value)} placeholder="项目亮点、培养模式等" />
                </Field>
              </div>
              <div className="btn-row">
                <button className="sup-primary" type="submit" disabled={busy}>{busy ? '提交中…' : '创建项目'}</button>
                <button className="btn-ghost" type="button" onClick={() => setCreating(false)}>取消</button>
              </div>
            </form>
          )}
        </div>
      )}

      {isStudent && mine.loading && <div className="sup-empty">正在核对签约状态…</div>}

      {isStudent && !mine.loading && signed && (
        <div className="enroll-box">
          <div className="enroll-head">
            <span className="enroll-badge">已签约</span>
            <b>我的课程</b>
            <small>{enrolled.length} 门在读</small>
          </div>
          <div className="enroll-list">
            {enrolled.map(x => (
              <div className="enroll-item" key={x.id}>
                <div>
                  <b>{x.project_name}</b>
                  <small>开通时间 {x.signed_at}</small>
                </div>
                <span className="enroll-status">{x.status}</span>
              </div>
            ))}
            {enrolled.length === 0 && <Empty>已签约，顾问正在为你开通课程</Empty>}
          </div>
        </div>
      )}

      {/* 未签约 = 系统里没有这个学生的课程，连项目清单也不给看 */}
      {isStudent && !mine.loading && !signed && (
        <div className="form-card locked-card">
          <h3>课程尚未开通</h3>
          <p className="hint-text">
            你的账号还没有签约记录。按平台规则，签约并选定课程后才会开通学生课程，
            未签约时不展示课程清单。
          </p>
          <div className="btn-row">
            {onGo && <button className="sup-primary" onClick={() => onGo('support')}>联系顾问签约</button>}
            {onGo && <button className="btn-ghost" onClick={() => onGo('home')}>返回工作台</button>}
          </div>
        </div>
      )}

      {(!isStudent || signed) && (
        <div className="panel-list">
          <h3>{signed ? '其它可报项目' : '课程 / 项目'} <small>{list.length} 个</small></h3>
          <div className="project-grid">
            {list.map(p => (
              <article className="soft-card" key={p.id}>
                <span className="tag">{p.category || '项目'}</span>
                <h3>{p.project_name}</h3>
                <p>{p.description}</p>
                <small>适合：{p.target_audience || '详情请咨询顾问'}</small>
              </article>
            ))}
            {!loading && !error && list.length === 0 && <Empty>暂无项目</Empty>}
          </div>
        </div>
      )}
    </div>
  )
}

/* ---------------- 健康检查（管理员） ---------------- */
export function HealthPanel() {
  const { data, loading, error } = useLoad(() => api('/api/health'), [])
  const ok = data && (data.status === 'ok' || data.status === 'healthy')
  const checkedAt = new Date().toLocaleString('zh-CN', { hour12: false })

  return (
    <div className="panel-body">
      <div className="form-card">
        <h3>后端连通性</h3>
        <Loader loading={loading} error={error} />
        {data && (
          <>
            <div className={ok ? 'health-ok' : 'health-bad'}>
              <span className="dot" />
              {ok ? 'FastAPI 接口正常，页面数据可以正常读写' : `接口返回异常：${data.status || '未知状态'}`}
            </div>
            <div className="kv-grid">
              <div><small>接口状态</small><b>{ok ? '正常' : '异常'}</b></div>
              <div><small>检查时间</small><b>{checkedAt}</b></div>
              <div><small>数据来源</small><b>本机 FastAPI :8000</b></div>
            </div>
            <p className="hint-text">接口异常时先确认后端是否在运行（run.bat），再看 <code>/api/health</code> 的返回。</p>
          </>
        )}
        <p className="hint-text">管理后台：<a href={ADMIN_URL} target="_blank" rel="noreferrer">{ADMIN_URL}</a></p>
      </div>
    </div>
  )
}

/* ---------------- 访客：咨询 / 画像 / 推荐 ---------------- */
export function ConsultPanel() {
  const ask = t => window.dispatchEvent(new CustomEvent('yuejiao-ask', { detail: { text: t, send: !!t } }))
  return (
    <div className="panel-body">
      <div className="form-card">
        <h3>先说说你的情况</h3>
        <p className="hint-text">年龄、现在读几年级、想去哪个国家、预算大概多少。说得越具体，推荐越准。</p>
        <div className="chip-row">
          {['19 岁高中毕业，想去新加坡读本科', '大专毕业想专升本，预算有限', '想了解德国双元制'].map(x => (
            <button key={x} className="chip" onClick={() => ask(x)}>{x}</button>
          ))}
        </div>
        <button className="sup-primary" onClick={() => ask('')}>打开智能顾问 →</button>
      </div>
    </div>
  )
}

function useRecommend() {
  const [raw, setRaw] = useState('')
  const [data, setData] = useState(null)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const run = async () => {
    if (!raw.trim() || busy) return
    setBusy(true); setMsg('')
    try {
      setData(await post('/api/recommend', { raw_text: raw.trim() }))
    } catch (e) {
      setMsg('分析失败：' + e.message)
    } finally { setBusy(false) }
  }
  return { raw, setRaw, data, msg, busy, run }
}

export function ProfilePanel() {
  const r = useRecommend()
  const p = r.data?.profile
  return (
    <div className="panel-body">
      <div className="form-card">
        <h3>画像信息抽取与归一化</h3>
        <Field label="用一段话描述学生情况">
          <textarea value={r.raw} onChange={e => r.setRaw(e.target.value)}
            placeholder="19岁高中刚毕业，想快点拿本科学历，预算一般，想去新加坡" />
        </Field>
        <button className="sup-primary" onClick={r.run} disabled={r.busy || !r.raw.trim()}>
          {r.busy ? '研判中…' : '开始研判'}
        </button>
        <Notice text={r.msg} />
      </div>
      {p && (
        <div className="form-card">
          <h3>归一化结果</h3>
          <div className="kv-grid">
            <div><span>年龄</span><b>{p.age || '未识别'}</b></div>
            <div><span>学历</span><b>{p.education || '未识别'}</b></div>
            <div><span>意向</span><b>{p.intent || '未识别'}</b></div>
            <div><span>语言</span><b>{p.language || '未识别'}</b></div>
            <div><span>动手/技能倾向</span><b>{p.hands_on ? '是' : '否'}</b></div>
          </div>
          <p className="hint-text">原始输入：{p.raw_text}</p>
        </div>
      )}
    </div>
  )
}

export function RecommendPanel() {
  const r = useRecommend()
  const matches = r.data?.matches || []
  return (
    <div className="panel-body">
      <div className="form-card">
        <h3>规则匹配与匹配度排序</h3>
        <Field label="学生情况（同画像研判的输入）">
          <textarea value={r.raw} onChange={e => r.setRaw(e.target.value)}
            placeholder="19岁高中刚毕业，想快点拿本科学历，预算一般，想去新加坡" />
        </Field>
        <button className="sup-primary" onClick={r.run} disabled={r.busy || !r.raw.trim()}>
          {r.busy ? '匹配中…' : '推荐项目'}
        </button>
        <Notice text={r.msg} />
      </div>
      {r.data?.summary && <div className="tip-strip">{r.data.summary}</div>}
      {matches.length > 0 && (
        <div className="match-list">
          {matches.map((m, i) => (
            <div className={'match-item' + (i === 0 ? ' best' : '')} key={m.project_id}>
              <div className="match-top">
                <b>{m.project_name}</b>
                <span className="match-score">{m.score} 分</span>
              </div>
              <div className="match-meta">{m.category}{i === 0 ? ' · 最佳匹配' : ''}</div>
              <p>{m.reason}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
