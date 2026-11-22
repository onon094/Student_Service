import { useEffect, useRef, useState } from 'react'

/**
 * 外观设置（折叠在齿轮里）
 * ------------------------------------------------------------
 * 上次把「折射强度 / 磨砂 / 深浅切换」直接铺在页面底部，那是开发时
 * 调参用的控件，普通使用者不该看到，也不该和「退出登录」挤在一起。
 * 现在统一收进这里：默认折叠，点齿轮才展开，点外面或按 ESC 收起。
 */
export default function AppearanceMenu({
  bgMode, setBgMode, light, setLight,
  veil, setVeil, strength, setStrength, blur, setBlur
}) {
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

  // 与身份菜单互斥，避免两个下拉叠在一起
  useEffect(() => {
    const h = e => { if (e.detail !== 'appearance') setOpen(false) }
    document.addEventListener('yuejiao-menu', h)
    return () => document.removeEventListener('yuejiao-menu', h)
  }, [])

  return (
    <div className="appearance" ref={boxRef}>
      <button className="gear-btn" onClick={() => {
        const next = !open
        setOpen(next)
        if (next) document.dispatchEvent(new CustomEvent('yuejiao-menu', { detail: 'appearance' }))
      }} title="外观设置">
        <span aria-hidden="true">⚙</span> 外观
      </button>

      {open && (
        <div className="appearance-menu">
          <div className="appearance-head">外观设置 <small>只影响显示，不影响功能</small></div>

          <div className="appearance-row">
            <span>背景</span>
            <div className="seg">
              <button className={bgMode === 'photo' ? 'on' : ''} onClick={() => setBgMode('photo')}>毕业照</button>
              <button className={bgMode === 'abstract' ? 'on' : ''} onClick={() => setBgMode('abstract')}>抽象渐变</button>
            </div>
          </div>

          {bgMode === 'photo' ? (
            <label className="appearance-row">
              <span>照片明暗 <b>{Math.round(veil * 100)}</b></span>
              <input type="range" min="0.25" max="0.85" step="0.05" value={veil}
                onChange={e => setVeil(Number(e.target.value))} />
            </label>
          ) : (
            <div className="appearance-row">
              <span>色调</span>
              <div className="seg">
                <button className={!light ? 'on' : ''} onClick={() => setLight(false)}>深色</button>
                <button className={light ? 'on' : ''} onClick={() => setLight(true)}>浅色</button>
              </div>
            </div>
          )}

          <label className="appearance-row">
            <span>玻璃折射 <b>{strength}</b></span>
            <input type="range" min="0" max="120" step="5" value={strength}
              onChange={e => setStrength(Number(e.target.value))} />
          </label>
          <label className="appearance-row">
            <span>磨砂程度 <b>{blur.toFixed(2)}</b></span>
            <input type="range" min="0" max="0.3" step="0.01" value={blur}
              onChange={e => setBlur(Number(e.target.value))} />
          </label>

          <button className="appearance-review" onClick={() => {
            window.dispatchEvent(new CustomEvent('yuejiao-review-open'))
          }}>
            页面批注：点着告诉我哪里别扭 →
          </button>
          <div className="appearance-foot">折射调低、照片调暗，文字会更清楚</div>
        </div>
      )}
    </div>
  )
}
