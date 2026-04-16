# 10_cross_end_e2e_lab/ros2_ws

本工作空间提供配套的 ROS2 模拟节点 `sorting_arm_mock`，用于课堂联调：

- 订阅：`/sorting_arm/cmd`（`std_msgs/msg/String`，`data` 内为 Envelope JSON 字符串）
- 发布：`/sorting_arm/status`（`std_msgs/msg/String`，`data` 内为 Envelope JSON 字符串）
- 同时发布 3 路可视化数据（均为 Envelope JSON）：
  - `/device/state_json`
  - `/device/params_json`
  - `/vision/detections_json`

## 构建与运行（ROS2 环境终端）

在 ROS2 环境终端执行：

```bash
cd 10_cross_end_e2e_lab/ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 run sorting_arm_mock arm_mock
```

- `colcon build --symlink-install`：构建并使用软链接方式安装，便于课堂快速修改代码。
- `source install/setup.bash`：刷新环境，让 `ros2 run` 能找到新包。
- `ros2 run sorting_arm_mock arm_mock`：启动模拟节点，配合 Web 项目完成端到端联调。

## 联调自检（Envelope）

1) 检查话题类型：

```bash
ros2 topic info -v /sorting_arm/cmd
ros2 topic info -v /sorting_arm/status
```

- 预期类型：`std_msgs/msg/String`（其中 `data` 是 JSON 字符串）。

2) 抓一条命令与一条回执，确认 `data` 是 Envelope JSON：

```bash
ros2 topic echo /sorting_arm/cmd --once
ros2 topic echo /sorting_arm/status --once
```

- 预期 `data` 形态：`{"schema_version":"1.0.0",...,"payload":{...}}`

