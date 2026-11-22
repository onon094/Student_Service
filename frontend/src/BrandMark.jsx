/**
 * 品牌标识
 * ------------------------------------------------------------
 * 半透明玻璃底 + 白色线条学士帽，跟随文字的 currentColor 变色。
 * 不再用实心蓝色方块，避免在玻璃导航上显得突兀。
 */
export default function BrandMark({ size = 34 }) {
  return (
    <svg
      className="brandmark"
      width={size} height={size} viewBox="0 0 40 40"
      role="img" aria-label="粤教服务"
      fill="none"
    >
      {/* 玻璃底：半透明填充 + 细描边 */}
      <rect x="0.6" y="0.6" width="38.8" height="38.8" rx="12"
        fill="currentColor" fillOpacity="0.1"
        stroke="currentColor" strokeOpacity="0.3" strokeWidth="1.1" />
      {/* 图形整体放大一点，避免小尺寸下留白过多 */}
      <g transform="translate(20 20) scale(1.16) translate(-20 -20)">
        {/* 学士帽 */}
        <path d="M20 11.4 31.2 16.2 20 21 8.8 16.2Z"
          stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeOpacity="0.95" />
        {/* 帽下托举弧线 */}
        <path d="M13.4 18.8v4.4c0 2.15 2.95 3.7 6.6 3.7s6.6-1.55 6.6-3.7v-4.4"
          stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeOpacity="0.78" />
        {/* 帽穗 */}
        <path d="M30.6 16.6v4.1" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeOpacity="0.55" />
        <circle cx="30.6" cy="21.7" r="1.1" fill="currentColor" fillOpacity="0.55" />
      </g>
    </svg>
  )
}
