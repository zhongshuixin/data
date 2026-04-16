# 10_cross_end_e2e_lab

跨端数据格式统一与联调测试（第 10 阶段综合实战项目）。

本项目将两类能力合并在同一个前端工程中：

- 数据面：Web 端通过 rosbridge 订阅 ROS2 话题，并做实时展示（监控面板 + 曲线）
- 控制面：Web 端通过 rosbridge 下发 ROS2 指令，并接收执行状态回传（cmd/status 闭环）

## 先决条件

- Node.js：建议使用课程统一版本（能运行 Vite + Vue3 即可）
- ROS2 + rosbridge 已启动（默认 `ws://localhost:9090`）
  - 如果你在宿主机访问虚拟机 rosbridge，可能需要端口映射（例如 `ws://localhost:19090`）

## 启动

在项目目录执行：

```bash
npm.cmd install
npm.cmd run dev
```

- `npm.cmd install`：安装依赖（PowerShell 执行策略限制时推荐用 `npm.cmd`）。
- `npm.cmd run dev`：启动开发服务器，浏览器打开终端输出的地址。

## 页面说明

- 实时监控：订阅 `/vision/detections_json`、`/device/state_json`、`/device/params_json`（默认 `std_msgs/msg/String`，`msg.data` 内为 JSON 字符串），展示卡片/表格/曲线。
- 指令下发：向 `/sorting_arm/cmd` 发布指令，并订阅 `/sorting_arm/status` 等待回执（按 `cmd_id/last_cmd_id` 关联）。

两个页面共用同一个 rosbridge URL 输入，并会自动保存到浏览器本地存储（下次打开自动恢复）。

## 协议与联调口径（统一）

- 本项目统一使用 Envelope（Envelope + Payload）作为跨端消息结构体。
- 指令下发 `/sorting_arm/cmd`：发送 `Envelope<ArmCommand>`。
- 状态回执 `/sorting_arm/status`：期望接收 `Envelope<ArmStatus>`。

## ROS2 配套模拟节点（建议用于课堂联调）

本项目自带 ROS2 工作空间：`10_cross_end_e2e_lab/ros2_ws`，内含包 `sorting_arm_mock`。

在 ROS2 环境终端执行：

```bash
cd 10_cross_end_e2e_lab/ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 run sorting_arm_mock arm_mock
```

- 该节点会发布 `/device/state_json`、`/device/params_json`、`/vision/detections_json`，保证“实时监控”页面有稳定可复现的数据源。
- 收到 `/sorting_arm/cmd` 后会回传 `/sorting_arm/status`，用于“指令下发”页面闭环联调。

## 典型联调步骤（建议）

1. 启动 rosbridge（9090 或你的映射端口）
2. 打开本项目，先进入“实时监控”，确认能订阅到数据（没有真实数据可用模拟话题发布）
3. 切换到“指令下发”，下发指令并观察 status 回执（按 `cmd_id/last_cmd_id` 关联）

## 关联讲义

- `23 跨端数据格式统一与联调测试 讲义（师生共用版・两课时）.md`
