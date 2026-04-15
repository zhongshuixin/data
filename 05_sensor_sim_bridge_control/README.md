# 05_sensor_sim_bridge_control

本示例用于演示一个最小闭环链路：

- Gazebo（Ignition Gazebo / `ign gazebo`）里仿真工业相机传感器
- 使用 `ros_gz_bridge` 将 Gazebo 传感器数据桥接到 ROS 2 话题
- ROS 2 节点订阅图像话题，触发发布一条机械臂关节目标（示例为 `Float64MultiArray`）

目录结构（核心）

- `ros2_ws/`：ROS 2 工作空间
  - `src/sensor_sim_bridge_control/`
    - `worlds/sorting_demo.world`：仿真世界（含相机传感器）
    - `launch/bringup.launch.py`：一键启动 Gazebo + bridge + 触发节点
    - `sensor_sim_bridge_control/image_trigger_arm.py`：图像触发发布控制指令的示例节点
    - `config/controllers.yaml`：ros2_control 控制器配置（用于教学扩展）

## 功能说明

### 1) Gazebo 相机仿真

`sorting_demo.world` 内包含一个 camera sensor：

- Gazebo 图像话题：`/sim/camera/rgb`
- Gazebo 相机内参话题：`/sim/camera/camera_info`

注意：world 中显式加载了 `Sensors` 系统插件以及基础插件（Physics / SceneBroadcaster / UserCommands），确保相机话题稳定发布。

### 2) Gazebo → ROS 2 桥接（ros_gz_bridge）

`bringup.launch.py` 会启动 `ros_gz_bridge parameter_bridge`，并做如下桥接与重映射：

- `/sim/camera/rgb` → `/camera/image_raw`（`sensor_msgs/msg/Image`）
- `/sim/camera/camera_info` → `/camera/camera_info`（`sensor_msgs/msg/CameraInfo`）

Gazebo 消息类型默认使用 `ignition.msgs.Image` 与 `ignition.msgs.CameraInfo`，并通过 launch 参数可覆盖。

### 3) 图像触发控制输出（image_trigger_arm）

`image_trigger_arm.py` 默认行为：

- 订阅 `/camera/image_raw`
- 收到第一帧图像后，向 `/arm_forward_controller/commands` 发布一次 `std_msgs/msg/Float64MultiArray`
- 默认 `one_shot=true`：只发布一次（用于演示“事件触发”）
- 提供服务：
  - `/image_trigger_arm/reset`：允许再次触发发布一次
  - `/image_trigger_arm/enable`：启用/禁用触发

## 环境依赖

- ROS 2 Humble
- Ignition Gazebo（`ign gazebo`，此环境为 ignition-gazebo6）
- `ros_gz_bridge`

## 如何运行

### 1) 编译工作空间

```bash
cd Module03_Simulation_Environment/05_sensor_sim_bridge_control/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### 2) 一键启动（推荐）

```bash
ros2 launch sensor_sim_bridge_control bringup.launch.py
```

常用可选参数（按需覆盖）：

- 切换 world 文件：
  - `world:=.../sorting_demo.world`
- 强制软件渲染（无 GPU 或驱动问题时）：
  - `libgl_always_software:=1`
- 覆盖桥接输出到 ROS 的话题名：
  - `image_topic:=/camera/image_raw`
  - `camera_info_topic:=/camera/camera_info`
- 覆盖 Gazebo 端消息类型（不同 Gazebo 版本可能不同）：
  - `gz_image_msg_type:=ignition.msgs.Image`
  - `gz_camera_info_msg_type:=ignition.msgs.CameraInfo`

示例：

```bash
ros2 launch sensor_sim_bridge_control bringup.launch.py \
  libgl_always_software:=1 \
  image_topic:=/camera/image_raw \
  camera_info_topic:=/camera/camera_info
```

## 如何验证是否“测试通过”

下面按链路分段验证，任意一步失败都能快速定位问题点。

### A. 验证 Gazebo 端相机话题

```bash
ign topic -l | grep /sim/camera
ign topic -e -t /sim/camera/rgb -n 1
ign topic -e -t /sim/camera/camera_info -n 1
```

预期：

- 能看到 `/sim/camera/rgb` 与 `/sim/camera/camera_info`
- `-e -n 1` 能回显一条消息（说明传感器确实在发布）

### B. 验证 ROS 端桥接话题

```bash
ros2 topic echo --once /camera/camera_info
ros2 topic echo --once /camera/image_raw
```

预期：

- `/camera/camera_info` 能打印出 `CameraInfo`（包含 width/height/K/P 等）
- `/camera/image_raw` 能打印出 `Image`（数据量较大，建议只看一次）

补充：桥接 QoS 由 bridge 节点决定；如果用 `ros2 topic echo` 收不到，优先用 `ros2 topic info -v <topic>` 查看 QoS 与发布者是否存在。

### C. 验证闭环触发输出（/arm_forward_controller/commands）

由于 `image_trigger_arm` 默认 `one_shot=true`，它可能在你开始 `echo` 之前就已经发布过一次，导致 `--once` 一直等不到下一条。

推荐验证方式：

1) 先打开监听：
```bash
ros2 topic echo /arm_forward_controller/commands
```

2) 触发重新发送一次：
```bash
ros2 service call /image_trigger_arm/reset std_srvs/srv/Trigger "{}"
```

预期：

- `commands` 话题能看到一条 `Float64MultiArray`（长度通常为 6，对应 6 个关节）

如果想持续触发便于调试：

```bash
ros2 param set /image_trigger_arm one_shot false
```

## 常见问题排查

### 1) `ros2 topic echo --once /camera/camera_info` 没输出

按顺序排查：

1) Gazebo 端是否真的在发：
   - `ign topic -e -t /sim/camera/camera_info -n 1`
2) bridge 是否在跑：
   - `ros2 node list | grep camera_bridge`
3) `bringup.launch.py` 中 bridge 的 Gazebo 话题名是否匹配当前版本：
   - 有些版本 camera_info 的话题不是 `/sim/camera/rgb/camera_info`，而是 `/sim/camera/camera_info`

### 2) `ros2 topic echo --once /arm_forward_controller/commands` 没输出

大概率是 one_shot 已经发过一次：

- 用 `/image_trigger_arm/reset` 让它再次发一次
- 或将 `one_shot` 设为 `false`

### 3) 日志目录权限问题（只在受限环境出现）

若看到类似 “Read-only file system: ~/.ros/log” 或 “~/.ignition/gazebo/log” 的报错：

- 确保 `~/.ros`、`~/.ignition` 可写
- 或将日志目录指向可写路径（示例）：
  - `export ROS_LOG_DIR=/tmp/ros_log`
  - `export IGN_LOG_PATH=/tmp/ign_log`

