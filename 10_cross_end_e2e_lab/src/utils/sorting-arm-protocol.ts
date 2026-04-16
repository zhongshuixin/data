// 机械臂控制面协议（与课程讲义一致）
// - Web → ROS2：向 /sorting_arm/cmd 发布 std_msgs/msg/String，其中 data 是 ArmCommand 的 JSON 字符串
// - ROS2 → Web：从 /sorting_arm/status 订阅 std_msgs/msg/String，其中 data 是 ArmStatus 的 JSON 字符串
// - 关联规则：cmd_id（请求） ↔ last_cmd_id（回执）
export type Role = 'viewer' | 'operator' | 'admin'

// 课堂最小动作集：可按真实设备能力扩展
export type ArmAction = 'home' | 'stop' | 'e_stop' | 'pick_place'

// 指令（应用层协议），承载在 std_msgs/msg/String.data
export type ArmCommand<TParams = Record<string, unknown>> = {
  // 指令唯一标识：用于审计追踪与回执匹配
  cmd_id: string
  // 场景名：用于多场景扩展（课堂固定为 sorting）
  scene: 'sorting'
  // 设备类型：用于多设备扩展（课堂固定为 arm）
  device_type: 'arm'
  // 设备实例 id：例如 arm_01
  device_id: string
  // 动作
  action: ArmAction
  // 动作参数（随 action 变化）
  params: TParams
  // 安全前置条件（课堂阶段可固定；真实项目应在设备侧强校验）
  safety: { require_enable: boolean; require_guard_closed: boolean }
  // 追踪字段：用于权限与审计（设备侧可先忽略，后续逐步纳入校验）
  meta?: { user: string; role: Role }
  // 发送端时间戳（ms）
  ts_ms: number
}

// 状态回执（应用层协议），承载在 std_msgs/msg/String.data
export type ArmStatus = {
  device_type: 'arm'
  device_id: string
  // 设备状态机：用于 UI 展示与联动
  state: 'idle' | 'running' | 'error' | 'estop'
  // 与请求 cmd_id 对齐：用于把“这条回执”匹配回“哪条指令”
  last_cmd_id: string
  // 执行结果三件套：ok/code/message
  ok: boolean
  code: 'OK' | 'DENY' | 'BAD_REQUEST' | 'EXEC_ERROR'
  message: string
  // 扩展信息：允许不同动作/设备携带额外字段
  detail?: Record<string, unknown>
  ts_ms: number
}
