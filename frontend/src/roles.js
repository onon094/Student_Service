/**
 * 身份 → 菜单 → 数据范围（单一事实来源）
 * ------------------------------------------------------------
 * 页面入口、工作台卡片、功能页可做的操作、顶部「数据范围」提示，
 * 全部从这里推导，避免「菜单藏了但接口还能查」的假权限。
 *
 * 真实账号来源（FastAPI /api/identity/*）：
 *   学生 5 人：student_zhang / student_li / student_wang / student_zhao / student_sun
 *   员工 4 人：teacher_chen（班主任）、sales_lin（普通员工）、leader_zhou（领导）、admin_sys（管理员）
 * 身份判定：employee_role ∈ {班主任, 老师, 教师} → 老师；管理员 → 开发管理员；其余 → 员工。
 */

export const ENTRY_ROLES = ['student', 'employee']

export const ENTRY_META = {
  student: {
    label: '学生',
    line: '账号登录',
    desc: '请假、售后、成绩、心理状态、课程与活动',
    sample: 'student_zhang'
  },
  employee: {
    label: '老师',
    line: '账号登录',
    desc: '审批、成绩录入、心理跟踪、客户与数据',
    sample: 'teacher_chen'
  },
}

// 每个身份的功能入口（工作台卡片 + 功能页 chips）
export const MENUS = {
  student: [
    { key: 'leaves', label: '我的请假', desc: '提交申请、看审批进度', tag: '请' },
    { key: 'feedback', label: '售后反馈', desc: '报修与投诉，看处理结果', tag: '工' },
    { key: 'scores', label: '我的成绩', desc: '各科分数与学期', tag: '分' },
    { key: 'psych', label: '心理状态', desc: '记录心情，获取关怀建议', tag: '心' },
    { key: 'projects', label: '课程 / 项目', desc: '可报读的项目与要求', tag: '项' },
    { key: 'events', label: '活动与报名', desc: '讲座开放日，一键报名', tag: '活' },
  ],
  employee: [
    { key: 'leaves', label: '请假审批', desc: '通过或驳回学生请假', tag: '批' },
    { key: 'feedback', label: '售后审批', desc: '处理工单并通知学生', tag: '售' },
    { key: 'scores', label: '成绩录入', desc: '录入与查看学生成绩', tag: '分' },
    { key: 'psych', label: '心理跟踪', desc: '预警、画像与跟进', tag: '心' },
    { key: 'leads', label: '意向客户', desc: '录入、查询、状态流转', tag: '客' },
    { key: 'reports', label: '员工日报', desc: '提交与查看日报', tag: '报' },
    { key: 'events', label: '活动与报名', desc: '活动与报名记录', tag: '活' },
    { key: 'projects', label: '课程 / 项目', desc: '项目清单与适配人群', tag: '项' }
  ],
  teacher: [
    { key: 'leaves', label: '请假审批', desc: '通过或驳回学生请假', tag: '批' },
    { key: 'feedback', label: '售后审批', desc: '处理工单并通知学生', tag: '售' },
    { key: 'scores', label: '成绩录入', desc: '录入与查看学生成绩', tag: '分' },
    { key: 'psych', label: '心理跟踪', desc: '预警、画像与跟进', tag: '心' },
    { key: 'leads', label: '意向客户跟踪', desc: '查看并推进客户状态', tag: '客' },
    { key: 'reports', label: '员工日报', desc: '提交与查看日报', tag: '报' }
  ],
  admin: [
    { key: 'leads', label: '意向客户', desc: '全量客户与状态流转', tag: '客' },
    { key: 'scores', label: '成绩管理', desc: '查看与录入', tag: '分' },
    { key: 'leaves', label: '请假审批', desc: '全量审批', tag: '请' },
    { key: 'feedback', label: '工单处理', desc: '全量解决与通知', tag: '工' },
    { key: 'psych', label: '心理与预警', desc: '预警、画像与更新', tag: '心' },
    { key: 'reports', label: '员工日报', desc: '全量日报', tag: '报' },
    { key: 'events', label: '活动与报名', desc: '活动与报名记录', tag: '活' },
    { key: 'projects', label: '课程 / 项目', desc: '项目清单', tag: '项' },
    { key: 'health', label: '健康检查', desc: '后端接口连通性', tag: '检' }
  ]
}

// 功能页顶部显示「你能看到什么、能做什么」，让权限边界可见
export const DATA_SCOPE = {
  leaves: {
    student: '只读取并提交 student_id = 本人 的请假',
    employee: '读取全部待审批请假，可通过或驳回',
    teacher: '读取全部待审批请假，可通过或驳回',
    admin: '全部读写'
  },
  feedback: {
    student: '只提交和查看本人的工单',
    employee: '查看全部工单，可填写处理结果并通知',
    teacher: '查看全部工单，可审批并通知',
    admin: '全部读写'
  },
  scores: {
    student: '只查看本人各科成绩',
    employee: '录入成绩 + 查看全部学生成绩',
    teacher: '录入成绩 + 查看全部学生成绩',
    admin: '全部读写'
  },
  psych: {
    student: '录入自己的情绪，只查看自己的画像',
    employee: '查看预警与画像，可更新跟进状态',
    teacher: '查看预警与画像，可更新跟进状态',
    admin: '全部读写'
  },
  leads: {
    employee: '录入客户、查询、推进状态',
    teacher: '查看客户并推进状态，不负责录入',
    admin: '全部读写'
  },
  reports: {
    employee: '提交与查看日报',
    teacher: '提交与查看日报',
    admin: '查看全部日报'
  },
  events: {
    student: '查看活动并报名',
    employee: '查看活动与报名记录',
    teacher: '查看活动与报名记录',
    admin: '查看活动与报名记录'
  },
  projects: {
    student: '签约开通后才显示课程清单',
    employee: '查看全部项目',
    teacher: '查看全部项目',
    admin: '查看全部项目'
  },
  health: {
    admin: '后端接口连通性检查'
  }
}

// 员工与管理员都属于「可审批、可录入」的后台角色
export const STAFF_ROLES = ['employee', 'teacher', 'admin']
export const isStaff = role => STAFF_ROLES.includes(role)
