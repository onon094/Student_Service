/**
 * 演示配置
 * ------------------------------------------------------------
 * 这里放的是 Dify「应用 API Key」，不是模型密钥。
 * 仅用于本机课程演示；正式上线应改由自己的后端代理 Dify，Key 不落前端。
 */
/**
 * 地址自动适配（一份代码同时支持三种场景）：
 * 1. 本机开发   localhost:5173        → 后端 localhost:8000，Dify localhost/v1
 * 2. 局域网分享 192.168.x.x:5173      → 后端 192.168.x.x:8000，Dify 同主机/v1
 * 3. 公网演示版  前端由后端同源托管（端口不是 5173）
 *                                     → API 走相对路径（同源），Dify 云端不可用
 *
 * 判断依据：开发/局域网用的是 Vite 开发服务器 5173；公网版由 FastAPI 同源托管，端口不是 5173。
 */
const LOC = typeof location !== 'undefined' ? location : { hostname: 'localhost', protocol: 'http:', port: '5173' }
const H = LOC.hostname || 'localhost'
const PROTO = LOC.protocol || 'http:'
const ORIGIN = `${PROTO}//${H}`

// 公网演示版：前端与后端同源（同一个域名+端口），API 用相对路径，浏览器自动拼当前域
export const PUBLIC_DEMO = LOC.port !== '5173'
export const API = PUBLIC_DEMO ? '' : `${ORIGIN}:8000`
export const DIFY = `${ORIGIN}/v1`
export const ADMIN_URL = PUBLIC_DEMO ? '' : `${ORIGIN}:9528`

// 身份 → Dify 助手（老师复用员工助手，管理员同）；guest 仅用于官网在线客服窗口
//
// 安全约定：真实 Key 不写进源码（会被公开）。
//   本机：放在项目根目录的 .env.local（已被 .gitignore 排除）
//   开源版：默认为空，使用者复制 .env.example 为 .env.local 后填自己的 Key
const ENV = (typeof import.meta !== 'undefined' && import.meta.env) ? import.meta.env : {}

export const KEYS = {
  student: ENV.VITE_DIFY_STUDENT || '',                                   // 留学生智能管家
  employee: ENV.VITE_DIFY_EMPLOYEE || '',                                 // 员工业务助手
  teacher: ENV.VITE_DIFY_TEACHER || ENV.VITE_DIFY_EMPLOYEE || '',         // 老师复用员工助手（审批/教学）
  admin: ENV.VITE_DIFY_ADMIN || ENV.VITE_DIFY_EMPLOYEE || '',             // 管理员全权限
  guest: ENV.VITE_DIFY_GUEST || ''                                        // 在线客服（官网窗口）
}

export const ASSISTANT_NAME = {
  student: '留学生智能管家',
  employee: '员工业务助手',
  teacher: '教学事务助手',
  admin: '管理员助手',
  guest: '在线客服'   // 官网右下角客服窗口，不对应可登录身份
}

export const ROLE_LABEL = {
  student: '学生',
  employee: '老师',
  teacher: '老师',
  admin: '开发管理员',
  guest: '在线客服'
}

export const ROLE_HINT = {
  student: '请假、成绩、售后反馈、心理状态、课程与活动',
  employee: '意向客户、学生数据、待办、日报、数据查询',
  teacher: '请假审批、售后审批、成绩录入、心理跟踪',
  admin: '全部功能 + 健康检查 + 管理后台'
}

export const SESSION_KEY = 'yuejiao_demo_session'
