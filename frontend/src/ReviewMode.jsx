import { useEffect, useRef, useState } from 'react'

/**
 * 页面批注（全局常驻）
 * ------------------------------------------------------------
 * 右下角常驻「批注」按钮：任何页面一点就开，不用改 URL、不用刷新。
 * 点页面元素 → 选问题类型 → 补一句期望 → 生成一段能直接发出去的文本。
 * 每条记录都带「当前页面 / 区块 / 元素」，避免只说“那个按钮有点怪”。
 */

const ISSUES = ['位置不对', '太大 / 太小', '太挤 / 太空', '看不清', '多余', '缺少功能', '看不懂']
const STORE = 'yuejiao_review_marks'

function labelOf(el) {
  const raw = el.getAttribute('aria-label') || el.getAttribute('title') ||
    el.innerText || el.value || el.getAttribute('placeholder') || ''
  const txt = raw.trim().replace(/\s+/g, ' ')
  const tag = el.tagName.toLowerCase()
  const role = tag === 'button' ? '按钮'
    : tag === 'a' ? '链接'
      : tag === 'input' ? '输入框'
        : tag === 'select' ? '下拉框'
          : tag === 'textarea' ? '输入区'
            : tag === 'tr' ? '表格行'
              : tag === 'img' ? '图片' : ''
  return `${role ? role + ' ' : ''}${txt ? '「' + txt.slice(0, 18) + '」' : '<' + tag + '>'}`
}

function sectionOf(el) {
  if (el.closest('.entry-page')) return '入口页'
  if (el.closest('.login-page')) return '登录页'
  if (el.closest('.nav-glass')) return '顶部导航'
  if (el.closest('.chat-widget') || el.closest('.assistant-bubble')) return '右下角助手'
  if (el.closest('.welcome')) return '欢迎区'
  if (el.closest('.card-grid')) return '功能卡片'
  if (el.closest('#support')) return '人工服务'
  if (el.closest('.crumb')) return '面包屑'
  if (el.closest('.view-head')) return '页面标题'
  if (el.closest('.menu-chips')) return '功能切换'
  if (el.closest('.form-card')) return '表单区'
  if (el.closest('.panel-list')) return '数据列表'
  if (el.closest('.appearance')) return '外观设置'
  if (el.closest('.footer')) return '页脚'
  return '页面其它区域'
}

// 当前在哪个页面：优先功能页标题，其次欢迎区大标题
function pageOf() {
  const el = document.querySelector('.view-head h2')
    || document.querySelector('.welcome h1')
    || document.querySelector('.entry-title')
    || document.querySelector('.login-brand h1')
  return el ? el.innerText.trim().replace(/\s+/g, ' ').slice(0, 22) : '页面'
}

export default function ReviewMode({ open, onOpen, onClose }) {
  const [marks, setMarks] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORE) || '[]') } catch { return [] }
  })
  const [pending, setPending] = useState(null)
  const [issue, setIssue] = useState('')
  const [note, setNote] = useState('')
  const [listOpen, setListOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const hovered = useRef(null)

  useEffect(() => { localStorage.setItem(STORE, JSON.stringify(marks)) }, [marks])

  // 悬停描边 + 点击拦截（批注期间不触发真实操作）
  useEffect(() => {
    if (!open) return
    const clear = () => {
      if (hovered.current) {
        hovered.current.style.outline = ''
        hovered.current.style.outlineOffset = ''
        hovered.current = null
      }
    }
    const onOver = e => {
      if (e.target.closest('.review-ui')) return
      if (hovered.current === e.target) return
      clear()
      hovered.current = e.target
      e.target.style.outline = '2px dashed #5aa9ff'
      e.target.style.outlineOffset = '2px'
    }
    const onClick = e => {
      if (e.target.closest('.review-ui')) return
      e.preventDefault()
      e.stopPropagation()
      setPending({ page: pageOf(), section: sectionOf(e.target), label: labelOf(e.target) })
      setIssue('')
      setNote('')
      setListOpen(false)
    }
    const onKey = e => {
      if (e.key !== 'Escape') return
      if (pending) { setPending(null); return }
      if (listOpen) { setListOpen(false); return }
      onClose()
    }
    document.addEventListener('mouseover', onOver, true)
    document.addEventListener('click', onClick, true)
    document.addEventListener('keydown', onKey)
    return () => {
      clear()
      document.removeEventListener('mouseover', onOver, true)
      document.removeEventListener('click', onClick, true)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, pending, listOpen, onClose])

  const save = () => {
    if (!pending || !issue) return
    setMarks(prev => [...prev, { ...pending, issue, note: note.trim(), at: Date.now() }])
    setPending(null)
    setIssue('')
    setNote('')
  }

  const asText = () => [
    `【粤教服务批注 · ${marks.length} 条】`,
    ...marks.map((m, i) =>
      `${i + 1}. [${m.page || '页面'} / ${m.section}] ${m.label} —— ${m.issue}${m.note ? '：' + m.note : ''}`)
  ].join('\n')

  const copyAll = async () => {
    const text = asText()
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      window.prompt('复制失败，请手动全选复制：', text)
    }
  }

  return (
    <>
      <button
        className={'rv-fab review-ui' + (open ? ' is-on' : '')}
        onClick={() => (open ? setListOpen(v => !v) : onOpen())}
        title={open ? '查看已记录的批注' : '开启批注：点页面元素记录问题'}
      >
        {open ? `批注 ${marks.length}` : '批注'}
      </button>

      {open && (
        <div className="rv-bar review-ui">
          <span className="rv-dot" />
          <b>批注中</b>
          <span>点元素记录问题，不会执行操作；切页请先退出</span>
          <button onClick={onClose}>退出</button>
        </div>
      )}

      {open && listOpen && (
        <div className="rv-panel review-ui">
          <div className="rv-panel-head">
            已记录 {marks.length} 条
            <button onClick={() => setListOpen(false)}>收起</button>
          </div>
          {marks.length === 0 && <div className="rv-empty">还没有记录。点页面上觉得别扭的地方。</div>}
          {marks.map((m, i) => (
            <div className="rv-item" key={m.at + i}>
              <div className="rv-item-top">
                <span>[{m.page || '页面'} / {m.section}] {m.label}</span>
                <button onClick={() => setMarks(prev => prev.filter((_, k) => k !== i))}>删</button>
              </div>
              <div className="rv-item-issue">{m.issue}{m.note ? '：' + m.note : ''}</div>
            </div>
          ))}
          <div className="rv-panel-foot">
            <button className="rv-primary" onClick={copyAll} disabled={!marks.length}>
              {copied ? '已复制 ✓' : '复制全部，发给我'}
            </button>
            {marks.length > 0 && <button onClick={() => setMarks([])}>清空</button>}
          </div>
        </div>
      )}

      {open && pending && (
        <div className="rv-pending review-ui">
          <div className="rv-pending-head">
            <span>{pending.page} / {pending.section}</span>
            <b>{pending.label}</b>
          </div>
          <div className="rv-chips">
            {ISSUES.map(x => (
              <button key={x} className={issue === x ? 'on' : ''} onClick={() => setIssue(x)}>{x}</button>
            ))}
          </div>
          <input
            value={note}
            onChange={e => setNote(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) save() }}
            placeholder="再补一句：你希望它变成什么样（可留空）"
          />
          <div className="rv-pending-foot">
            <button onClick={() => setPending(null)}>取消</button>
            <button className="rv-primary" onClick={save} disabled={!issue}>记下这条</button>
          </div>
        </div>
      )}
    </>
  )
}
