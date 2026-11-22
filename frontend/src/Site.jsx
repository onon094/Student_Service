import { useEffect, useRef, useState } from 'react'
import BrandMark from './BrandMark.jsx'
import { api, post } from './ui.jsx'
import {
  ABOUT, BRAND, CASES, FAQ, HISTORY, HONORS, NAV, PARTNERS, PROCESS, SERVICES, STATS
} from './siteData.js'

/**
 * 官网首页
 * ------------------------------------------------------------
 * 未登录时看到的就是这个页面：公司介绍、主营业务、流程、成果、历程、资质、联系表单。
 * 内部系统入口收进右上角「登录」，不再把「选择身份」当首页。
 *
 * 提交咨询表单会真实创建一条客户线索（CRM），员工端「意向客户」立刻能看到，
 * 这样「官网获客 → 线索 → 签约 → 建账号 → 开课」是一条真链路。
 */
export default function Site({ onLogin, onAsk }) {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [faqOpen, setFaqOpen] = useState(0)

  // 咨询表单
  const [form, setForm] = useState({ name: '', phone: '', intent: '新加坡本科', note: '' })
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState(null)

  // 快速评估卡
  const [quiz, setQuiz] = useState({ edu: '高中在读', country: '新加坡', budget: '15–25 万/年' })

  const formRef = useRef(null)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const goto = id => {
    setMenuOpen(false)
    const el = document.querySelector(id)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const askWithQuiz = () => {
    const q = `我是${quiz.edu}，想去${quiz.country}，预算${quiz.budget}，想了解适合我的升学路径。`
    onAsk(q)
  }

  const submitLead = async e => {
    e.preventDefault()
    if (busy) return
    if (!form.name.trim()) return setMsg('请填写称呼')
    if (!/^1[3-9]\d{9}$|^\d{7,15}$/.test(form.phone.trim())) return setMsg('请填写有效的手机号')

    setBusy(true); setMsg('')
    try {
      // 官网是匿名场景，绝不调用需要鉴权的接口（否则 401 会触发全局"登录已过期"弹窗）。
      // 归属人直接用默认顾问（林顾问 id=7）；后端也会对官网线索做兜底归属。
      const owner = 7

      const d = await post('/api/employee/leads', {
        customer_name: form.name.trim(),
        contact_info: form.phone.trim(),
        background_info: [
          `官网咨询｜意向：${form.intent}`,
          form.note.trim() ? `留言：${form.note.trim()}` : ''
        ].filter(Boolean).join('；'),
        follow_up_history: '官网表单提交',
        owner_employee_id: owner
      })
      setCreated(d)
      setForm({ name: '', phone: '', intent: '新加坡本科', note: '' })
      setMsg('提交成功，顾问会在 1 个工作日内联系你')
    } catch (err) {
      setMsg('提交失败：' + err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="site">
      {/* ================= 顶部导航 ================= */}
      <header className={'site-nav' + (scrolled ? ' is-solid' : '')}>
        <div className="site-nav-inner">
          <a className="site-brand" href="#top" onClick={e => { e.preventDefault(); goto('#top') }}>
            <BrandMark size={36} />
            <span className="site-brand-txt">
              粤教服务
              <small>{BRAND.en}</small>
            </span>
          </a>

          <nav className={'site-menu' + (menuOpen ? ' is-open' : '')}>
            {NAV.map(n => (
              <a key={n.href} href={n.href} onClick={e => { e.preventDefault(); goto(n.href) }}>{n.label}</a>
            ))}
          </nav>

          <div className="site-nav-right">
            <a className="site-tel" href={`tel:${BRAND.phoneRaw}`}>
              <span className="tel-ico">☎</span>{BRAND.phone}
            </a>
            <button className="site-login" onClick={onLogin}>登录</button>
            <button className="site-burger" onClick={() => setMenuOpen(v => !v)} aria-label="菜单">
              {menuOpen ? '✕' : '☰'}
            </button>
          </div>
        </div>
      </header>

      {/* ================= 首屏 ================= */}
      <section className="site-hero" id="top">
        <div className="site-hero-inner">
          <div className="site-hero-copy">
            <span className="eyebrow">国际教育 · 留学全流程服务 · 成立于 2013 年</span>
            <h1>{BRAND.slogan}</h1>
            <p>{BRAND.sub}</p>
            <div className="hero-btns">
              <button className="btn-main" onClick={() => goto('#contact')}>免费获取方案</button>
              <button className="btn-line" onClick={() => goto('#services')}>查看课程与项目 →</button>
            </div>
            <div className="hero-trust">
              <span>✓ 未录取按合同退费</span>
              <span>✓ 一位顾问跟到底</span>
              <span>✓ 境外落地有团队</span>
            </div>
          </div>

          {/* 快速评估卡 */}
          <div className="quiz-card">
            <h3>30 秒预估你的路径</h3>
            <p className="quiz-sub">选三项，直接给你一份可执行的判断</p>

            <label className="quiz-field">
              <span>当前学历</span>
              <select value={quiz.edu} onChange={e => setQuiz({ ...quiz, edu: e.target.value })}>
                {['初中毕业', '高中在读', '高中毕业', '大专在读', '大专毕业', '本科在读', '本科毕业'].map(x =>
                  <option key={x} value={x}>{x}</option>)}
              </select>
            </label>

            <label className="quiz-field">
              <span>意向国家 / 地区</span>
              <select value={quiz.country} onChange={e => setQuiz({ ...quiz, country: e.target.value })}>
                {['新加坡', '德国', '还没想好'].map(x =>
                  <option key={x} value={x}>{x}</option>)}
              </select>
            </label>

            <label className="quiz-field">
              <span>每年预算</span>
              <select value={quiz.budget} onChange={e => setQuiz({ ...quiz, budget: e.target.value })}>
                {['8 万以内', '8–15 万/年', '15–25 万/年', '25–35 万/年', '35 万以上', '希望免学费'].map(x =>
                  <option key={x} value={x}>{x}</option>)}
              </select>
            </label>

            <button className="btn-main quiz-btn" onClick={askWithQuiz}>让智能助手先帮我判断</button>
            <small className="quiz-note">不想聊？填个电话让顾问联系你 → <a href="#contact" onClick={e => { e.preventDefault(); goto('#contact') }}>留联系方式</a></small>
          </div>
        </div>
      </section>

      {/* ================= 数据条 ================= */}
      <section className="site-stats">
        <div className="site-stats-inner">
          {STATS.map(s => (
            <div className="stat" key={s.label}>
              <b>{s.value}</b>
              <span>{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ================= 关于我们 ================= */}
      <section className="site-sec" id="about">
        <div className="sec-head">
          <span className="sec-tag">关于我们</span>
          <h2>{ABOUT.title}</h2>
          <p className="sec-lead">{ABOUT.lead}</p>
        </div>

        <div className="about-grid">
          <div className="about-text">
            {ABOUT.paras.map((p, i) => <p key={i}>{p}</p>)}
          </div>
          <div className="about-points">
            {ABOUT.points.map(p => (
              <div className="about-point" key={p.t}>
                <b>{p.t}</b>
                <span>{p.d}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= 主营业务 ================= */}
      <section className="site-sec" id="services">
        <div className="sec-head">
          <span className="sec-tag">主营业务</span>
          <h2>六条主要升学路径，覆盖不同分数与预算</h2>
          <p className="sec-lead">不是每个学生都适合直申。先判断条件，再推荐路径，这是我们和「保录取」机构最大的区别。</p>
        </div>

        <div className="svc-grid">
          {SERVICES.map(s => (
            <article className="svc-card" key={s.title}>
              {s.tag && <span className="svc-tag">{s.tag}</span>}
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
              <ul>
                {s.points.map(p => <li key={p}>{p}</li>)}
              </ul>
              <button className="svc-more" onClick={() => askWithQuiz()}>问助手这条路径 →</button>
            </article>
          ))}
        </div>
      </section>

      {/* ================= 服务流程 ================= */}
      <section className="site-sec site-sec-alt" id="process">
        <div className="sec-head">
          <span className="sec-tag">服务流程</span>
          <h2>从第一次咨询到落地报到，五步走完</h2>
        </div>

        <ol className="flow">
          {PROCESS.map((p, i) => (
            <li className="flow-step" key={p.n}>
              <span className="flow-n">{p.n}</span>
              <div>
                <b>{p.t}</b>
                <p>{p.d}</p>
              </div>
              {i < PROCESS.length - 1 && <span className="flow-line" />}
            </li>
          ))}
        </ol>
      </section>

      {/* ================= 成果与案例 ================= */}
      <section className="site-sec" id="results">
        <div className="sec-head">
          <span className="sec-tag">成果案例</span>
          <h2>不吹录取率，给你看三个真实起点</h2>
          <p className="sec-lead">以下为脱敏后的学员情况，成绩、预算、录取结果均为实际记录（姓名已隐去）。</p>
        </div>

        <div className="case-grid">
          {CASES.map(c => (
            <article className="case-card" key={c.name}>
              <div className="case-top">
                <b>{c.name}</b>
                <span>{c.tag}</span>
              </div>
              <div className="case-row">
                <small>起点</small>
                <p>{c.before}</p>
              </div>
              <div className="case-row">
                <small>结果</small>
                <p>{c.result}</p>
              </div>
              <blockquote>{c.quote}</blockquote>
            </article>
          ))}
        </div>

        <div className="partner-strip">
          <span className="partner-label">合作院校与机构</span>
          <div className="partner-tags">
            {PARTNERS.map(p => <span key={p}>{p}</span>)}
          </div>
        </div>

        <div className="honor-grid">
          {HONORS.map(h => (
            <div className="honor" key={h.t}>
              <span className="honor-ico">✓</span>
              <div>
                <b>{h.t}</b>
                <small>{h.d}</small>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ================= 发展历程 ================= */}
      <section className="site-sec site-sec-alt" id="history">
        <div className="sec-head">
          <span className="sec-tag">发展历程</span>
          <h2>13 年，从单一国家到全流程数字化</h2>
        </div>

        <div className="timeline">
          {HISTORY.map(h => (
            <div className="tl-item" key={h.year}>
              <span className="tl-year">{h.year}</span>
              <div className="tl-body">
                <b>{h.title}</b>
                <p>{h.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ================= 常见问题 ================= */}
      <section className="site-sec">
        <div className="sec-head">
          <span className="sec-tag">常见问题</span>
          <h2>家长最常问的四个问题</h2>
        </div>
        <div className="faq-list">
          {FAQ.map((f, i) => (
            <div className={'faq-item' + (faqOpen === i ? ' is-open' : '')} key={f.q}>
              <button className="faq-q" onClick={() => setFaqOpen(faqOpen === i ? -1 : i)}>
                <span>{f.q}</span>
                <span className="faq-ico">{faqOpen === i ? '−' : '+'}</span>
              </button>
              {faqOpen === i && <p className="faq-a">{f.a}</p>}
            </div>
          ))}
        </div>
      </section>

      {/* ================= 联系我们 ================= */}
      <section className="site-sec site-contact" id="contact" ref={formRef}>
        <div className="contact-grid">
          <div className="contact-info">
            <span className="sec-tag">联系我们</span>
            <h2>先聊清楚情况，再谈方案</h2>
            <p className="sec-lead">
              留个联系方式，顾问会在一个工作日内回电；也可以直接打电话或到店面谈，
              第一次咨询不收费。
            </p>

            <div className="contact-list">
              <div><small>咨询热线</small><b>{BRAND.phone}</b><span>{BRAND.hours}</span></div>
              <div><small>邮箱</small><b>{BRAND.email}</b><span>材料与合作请发邮件</span></div>
              <div><small>办公地址</small><b>{BRAND.address}</b><span>地铁 5 号线猎德站 B 出口步行 6 分钟</span></div>
            </div>

            <div className="contact-tip">
              到店面谈建议提前预约，我们会安排对应国家的顾问在场。
            </div>
          </div>

          <form className="contact-form" onSubmit={submitLead}>
            <h3>免费咨询预约</h3>
            <div className="cf-row">
              <label>
                <span>称呼</span>
                <input value={form.name} placeholder="如 王女士"
                  onChange={e => { setForm({ ...form, name: e.target.value }); setMsg('') }} />
              </label>
              <label>
                <span>手机号</span>
                <input value={form.phone} placeholder="顾问回电用"
                  onChange={e => { setForm({ ...form, phone: e.target.value }); setMsg('') }} />
              </label>
            </div>
            <label>
              <span>意向方向</span>
              <select value={form.intent} onChange={e => setForm({ ...form, intent: e.target.value })}>
                {['新加坡本科', '新加坡本硕连读', '德国双元制', '语言培训', '还没确定'].map(x => <option key={x} value={x}>{x}</option>)}
              </select>
            </label>
            <label>
              <span>简单说下情况（选填）</span>
              <textarea value={form.note} placeholder="如：孩子高三，预估 450 分，预算每年 15 万左右"
                onChange={e => setForm({ ...form, note: e.target.value })} />
            </label>

            <button className="btn-main cf-submit" type="submit" disabled={busy}>
              {busy ? '提交中…' : '提交，等顾问联系我'}
            </button>

            {msg && <div className={'cf-msg' + (created ? ' ok' : '')}>{msg}</div>}
            {created && (
              <div className="cf-done">
                已生成咨询编号 <b>#{created.id}</b>，负责人会在工作台看到这条线索。
              </div>
            )}
            <small className="cf-note">提交即表示同意我们通过电话或短信联系你，信息仅用于咨询，不做其它用途。</small>
          </form>
        </div>
      </section>

      {/* ================= 页脚 ================= */}
      <footer className="site-footer">
        <div className="footer-main">
          <div className="footer-brand">
            <div className="site-brand">
              <BrandMark size={36} />
              <span className="site-brand-txt">粤教服务<small>{BRAND.en}</small></span>
            </div>
            <p>{BRAND.slogan}。国际教育升学规划与境外落地服务。</p>
            <div className="footer-contact">
              <span>{BRAND.phone}</span>
              <span>{BRAND.email}</span>
            </div>
          </div>

          <div className="footer-col">
            <b>主营业务</b>
            {['新加坡本科', '德国双元制'].map(x => <span key={x}>{x}</span>)}
          </div>
          <div className="footer-col">
            <b>关于</b>
            {['公司介绍', '发展历程', '资质荣誉', '加入我们'].map(x => <span key={x}>{x}</span>)}
          </div>
          <div className="footer-col">
            <b>服务</b>
            <span>免费评估</span>
            <span>材料清单</span>
            <span>行前指导</span>
            <button className="footer-login" onClick={onLogin}>学员 / 员工登录 →</button>
          </div>
        </div>

        <div className="footer-bottom">
          <span>© 2013–2026 {BRAND.name} 版权所有</span>
          <span>{BRAND.icp}</span>
          <span>地址：{BRAND.address}</span>
        </div>
      </footer>
    </div>
  )
}
