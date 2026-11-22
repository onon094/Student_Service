import { useEffect, useRef, useState } from 'react'
import { ASSISTANT_NAME, DIFY, PUBLIC_DEMO, ROLE_LABEL } from './config.js'

const QUICK = {
  student: ['查一下我的成绩', '我要请一天假', '最近压力有点大'],
  employee: ['查一下客户线索', '录入成绩：学号1 Python 92分', '写日报：今天跟进3个客户', '看看心理预警'],
  admin: ['一共有多少个学生', '看看心理预警', '查一下客户线索'],
  guest: ['粤教服务主要做什么？', '19岁高中毕业能读什么项目？', '近期有什么活动？']
}

const OPEN_KEY = 'yuejiao_chat_open'
const LARGE_KEY = 'yuejiao_chat_large'

// 极简 Markdown：先转义防注入，再处理加粗与换行（演示够用，不引第三方库）
function renderText(s) {
  return s
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>')
}

export default function ChatWidget({ session }) {
  // 展开 / 大小都记住上次状态：刷新后不会又突然弹出来挡住页面
  const [open, setOpen] = useState(() => localStorage.getItem(OPEN_KEY) === '1')
  const [large, setLarge] = useState(() => localStorage.getItem(LARGE_KEY) === '1')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [convId, setConvId] = useState('')
  const [error, setError] = useState('')
  const abortRef = useRef(null)
  const busyRef = useRef(false)
  const sendRef = useRef(null)
  const bodyRef = useRef(null)
  const firstSession = useRef(true)

  useEffect(() => { localStorage.setItem(OPEN_KEY, open ? '1' : '0') }, [open])
  useEffect(() => { localStorage.setItem(LARGE_KEY, large ? '1' : '0') }, [large])

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages])

  // 首页 / 工作台送过来的问题：send=true 时「点一下就直接问」，
  // 不再只是把字填进输入框、还要用户再点一次发送。
  useEffect(() => {
    const handler = e => {
      const d = typeof e.detail === 'string' ? { text: e.detail, send: false } : (e.detail || {})
      setOpen(true)
      if (d.send && d.text) {
        setTimeout(() => sendRef.current?.(d.text), 0)
      } else {
        setInput(d.text || '')
        setTimeout(() => document.querySelector('.chat-widget textarea')?.focus(), 0)
      }
    }
    window.addEventListener('yuejiao-ask', handler)
    return () => window.removeEventListener('yuejiao-ask', handler)
  }, [])

  // 开批注时自动收起助手，避免挡住要标注的内容
  useEffect(() => {
    const close = () => setOpen(false)
    window.addEventListener('yuejiao-close-chat', close)
    return () => window.removeEventListener('yuejiao-close-chat', close)
  }, [])

  // 切换身份后清空会话，但给一条明确说明，避免看起来像「消息丢了」
  useEffect(() => {
    if (firstSession.current) { firstSession.current = false; return }
    // 官网客服窗口没有「身份切换」概念，不弹这条提示
    if (session.role === 'guest') return
    setMessages([{
      role: 'notice',
      text: `已切换为 ${ROLE_LABEL[session.role]} · ${session.realName}，对话已重新开始`
    }])
    setConvId('')
    setError('')
    setInput('')
  }, [session.username, session.role])

  // ESC：大窗先缩回小窗，小窗再收起（符合弹层的常规习惯）
  useEffect(() => {
    const onKey = e => {
      if (e.key !== 'Escape' || !open) return
      if (large) setLarge(false)
      else setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, large])

  const stop = () => { if (abortRef.current) abortRef.current.abort() }

  const clear = () => {
    stop()
    setMessages([])
    setConvId('')
    setError('')
  }

  const send = async (preset) => {
    const q = (preset ?? input).trim()
    if (!q || busyRef.current) return
    busyRef.current = true
    setInput('')
    setError('')

    const aiIndex = messages.length + 1
    setMessages(prev => [...prev, { role: 'user', text: q }, { role: 'ai', text: '' }])
    setSending(true)

    // 公网演示版：Dify 只跑在本地 Docker，云端没有；直接给友好提示，不发起注定失败的请求。
    // 其余功能（登录、数据查询、请假、报名、推荐等）走后端 API，云端照常可用。
    if (PUBLIC_DEMO) {
      setMessages(prev => {
        const copy = prev.slice()
        copy[aiIndex] = {
          role: 'ai',
          text: '这是在线演示版：智能对话由本地 Dify 提供服务，云端暂未接入。你可以体验其余完整功能——登录、自然语言查数据、画像推荐、请假审批、活动报名、客户管理等。本地运行时本助手可正常使用。'
        }
        return copy
      })
      setSending(false)
      busyRef.current = false
      return
    }

    const ctrl = new AbortController()
    abortRef.current = ctrl
    let answer = ''

    try {
      const res = await fetch(`${DIFY}/chat-messages`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.key}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          inputs: {},
          query: q,
          response_mode: 'streaming',
          conversation_id: convId,
          user: session.username || 'guest'
        }),
        signal: ctrl.signal
      })
      if (!res.ok) throw new Error(`接口返回 HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        let nl
        while ((nl = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, nl).trim()
          buffer = buffer.slice(nl + 1)
          if (!line.startsWith('data:')) continue   // event: ping 等心跳直接跳过
          const raw = line.slice(5).trim()
          if (!raw) continue
          let data
          try { data = JSON.parse(raw) } catch { continue }

          if (data.conversation_id) setConvId(data.conversation_id)
          if (data.event === 'message') {
            answer += data.answer || ''
            setMessages(prev => {
              const copy = prev.slice()
              copy[aiIndex] = { role: 'ai', text: answer }
              return copy
            })
          } else if (data.event === 'error' || data.event === 'message_error') {
            throw new Error(data.message || '生成失败')
          }
        }
      }

      if (!answer) {
        setMessages(prev => {
          const copy = prev.slice()
          copy[aiIndex] = { role: 'ai', text: '（助手没有返回内容，请重试或换个问法）' }
          return copy
        })
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        setMessages(prev => {
          const copy = prev.slice()
          copy[aiIndex] = { role: 'ai', text: answer || '（已停止生成）' }
          return copy
        })
      } else {
        setError(e.message || '请求失败')
        setMessages(prev => {
          const copy = prev.slice()
          copy[aiIndex] = { role: 'ai', text: `抱歉，${e.message || '请求失败'}。请确认 Dify 与后端都在运行。` }
          return copy
        })
      }
    } finally {
      setSending(false)
      busyRef.current = false
      abortRef.current = null
    }
  }
  sendRef.current = send

  if (!open) {
    return (
      <button className="assistant-bubble" onClick={() => setOpen(true)}>
        <span className="bubble-dot" />
        问问{ASSISTANT_NAME[session.role]}
      </button>
    )
  }

  return (
    <>
      {large && <div className="chat-overlay" onClick={() => setLarge(false)} />}
      <div className={'chat-widget ' + (large ? 'chat-large' : '')}>
        <div className="chat-head">
          <div className="chat-title">
            <b>{ASSISTANT_NAME[session.role]}</b>
            <small>{session.role === 'guest' ? '官网在线咨询' : `${ROLE_LABEL[session.role]} · ${session.realName}`}</small>
          </div>
          <div className="chat-actions">
            <button
              onClick={() => { setOpen(false); document.getElementById('support')?.scrollIntoView({ behavior: 'smooth' }) }}
              title="转人工：留言或查看处理进度"
            >
              人工
            </button>
            <button onClick={() => setLarge(v => !v)} title="切换大小">{large ? '缩小' : '放大'}</button>
            <button onClick={clear} title="清空会话">清空</button>
            <button onClick={() => setOpen(false)} title="收起（也可按 ESC）">收起</button>
          </div>
        </div>

        <div className="chat-body" ref={bodyRef}>
          {messages.length === 0 && (
            <div className="chat-welcome">
              <p>你好{session.role === 'guest' ? '，欢迎咨询' : `，${session.realName}`}。我是{ASSISTANT_NAME[session.role]}，可以试试下面这些问题：</p>
              <div className="quick-list">
                {QUICK[session.role].map(q => (
                  <button key={q} onClick={() => send(q)}>{q}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => m.role === 'notice'
            ? <div className="chat-notice" key={i}>{m.text}</div>
            : (
              <div key={i} className={'msg msg-' + m.role}>
                <div className="bubble"
                  dangerouslySetInnerHTML={{ __html: m.text ? renderText(m.text) : '<span class="typing">思考中…</span>' }} />
              </div>
            ))}
          {error && <div className="chat-error">{error}</div>}
        </div>

        <div className="chat-foot">
          <textarea
            value={input}
            placeholder="输入问题，Enter 发送 / Shift+Enter 换行"
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
            }}
          />
          <div className="chat-buttons">
            <span>{sending ? '正在生成…' : ''}</span>
            {sending
              ? <button className="btn-stop" onClick={stop}>停止</button>
              : <button className="btn-send" onClick={() => send()}>发送</button>}
          </div>
        </div>
      </div>
    </>
  )
}
