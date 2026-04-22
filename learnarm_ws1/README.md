# learnarm_ws 工作空间

## 项目概述

learnarm_ws 是一个基于 ROS 2 Humble 的机械臂学习工作空间，包含机械臂控制、运动规划和仿真配置等功能模块。

## 工作空间结构

```
learnarm_ws/
├── src/                          # 源代码目录
│   ├── arm1/                     # 机械臂控制包
│   ├── motion_api/               # 运动规划API包
│   └── robot_arm_config/         # 机械臂配置包
├── build/                        # 构建目录
├── install/                      # 安装目录
└── log/                          # 日志目录
```

## 包说明

### 1. arm1 包

**功能**: 机械臂基础控制包，提供机械臂的URDF模型、控制器配置和启动文件。

**主要组件**:
- **URDF模型**: 定义机械臂的几何结构和物理属性
  - `robot_arm_ros2_controller.urdf` - 集成ros2_control的URDF文件
  - `robot_arm.urdf` - 基础URDF文件
  - `robot.urdf` - 机器人URDF文件

- **控制器配置**: `config/arm_controllers.yaml`
  - arm_controller: 机械臂关节控制器
  - hand_controller: 夹爪控制器
  - joint_state_broadcaster: 关节状态广播器

- **启动文件**:
  - `robot_arm_ros2_control_launch.py` - 完整的ros2_control启动文件
  - `robot_arm_action_ros2_control_launch.py` - 基于Action的控制启动
  - `robot_arm_hand_ros2_control_launch.py` - 夹爪控制启动
  - `robot_arm_publisher_ros2_control_launch.py` - 状态发布器启动
  - `show_urdf_launch.py` - URDF可视化启动

- **测试脚本**:
  - `test_arm_action.py` - Action控制测试
  - `test_arm_hand.py` - 夹爪控制测试
  - `test_arm_publisher.py` - 状态发布器测试

**依赖项**:
- rclpy, std_msgs
- robot_state_publisher
- joint_state_publisher_gui
- rviz2, xacro
- ros2_control, controller_manager
- joint_trajectory_controller
- forward_command_controller
- joint_state_broadcaster

### 2. motion_api 包

**功能**: 基于 MoveItPy 的运动规划API包，提供机械臂运动规划和抓取操作的Python接口。

**主要组件**:
- **运动规划模块**:
  - `motion_planning_python_api.py` - MoveItPy运动规划API
  - `pick_rose_drop.py` - 抓取玫瑰并放置的示例
  - `pick_drop.py` - 基础抓取放置功能

- **配置文件**:
  - `moveit_cpp.yaml` - MoveIt C++接口配置
  - `blue.urdf`, `green.urdf`, `red.urdf` - 不同颜色的物体URDF
  - `pink_cylinder.sdf` - 粉色圆柱体SDF模型

- **启动文件**:
  - `motion_api.launch.py` - 运动规划API启动
  - `load_all_models.launch.py` - 加载所有模型
  - `pick_block.launch.py` - 抓取方块演示

**可执行程序**:
- `motion_api_test` - 运动规划测试
- `pick_drop` - 抓取放置程序
- `pick_rose_drop` - 玫瑰抓取程序

### 3. robot_arm_config 包

**功能**: MoveIt配置包，由MoveIt Setup Assistant自动生成，提供完整的运动规划配置。

**主要组件**:
- **URDF/XACRO配置**:
  - `arm.urdf.xacro` - 机械臂XACRO模型
  - `arm.ros2_control.xacro` - ros2_control配置
  - `arm.gazebo.urdf.xacro` - Gazebo仿真配置
  - `arm.gazebo.ros2_control.xacro` - Gazebo控制配置

- **MoveIt配置**:
  - `arm.srdf` - 语义机器人描述文件
  - `kinematics.yaml` - 运动学求解器配置
  - `joint_limits.yaml` - 关节限制配置
  - `moveit_controllers.yaml` - MoveIt控制器配置
  - `ros2_controllers.yaml` - ROS 2控制器配置
  - `pilz_cartesian_limits.yaml` - 笛卡尔路径限制

- **初始配置**:
  - `initial_positions.yaml` - 关节初始位置
  - `moveit.rviz` - RViz配置文件

- **启动文件**:
  - `demo.launch.py` - 基础演示
  - `full_demo.launch.py` - 完整演示
  - `gazebo.launch.py` - Gazebo仿真启动
  - `move_group.launch.py` - MoveIt运动组启动
  - `moveit_rviz.launch.py` - RViz可视化启动
  - `rsp.launch.py` - 机器人状态发布器启动
  - `spawn_controllers.launch.py` - 控制器生成
  - `warehouse_db.launch.py` - 仓库数据库启动

**依赖项**:
- moveit_ros_move_group, moveit_kinematics
- moveit_planners, moveit_simple_controller_manager
- joint_state_publisher, joint_state_publisher_gui
- tf2_ros, xacro, arm1
- controller_manager, moveit_configs_utils
- moveit_ros_visualization, moveit_ros_warehouse
- moveit_setup_assistant, robot_state_publisher
- rviz2, rviz_common, rviz_default_plugins
- warehouse_ros_mongo

## 机械臂规格

### 关节配置
- **joint1**: 基座旋转关节
- **joint2**: 肩部俯仰关节
- **joint3**: 肘部俯仰关节
- **joint4**: 腕部旋转关节
- **joint5**: 腕部俯仰关节
- **joint6**: 腕部旋转关节
- **hand_right_joint**: 夹爪关节

### 控制接口
- **命令接口**: position（位置控制）
- **状态接口**: position（位置）、velocity（速度）

## 使用方法

### 1. 环境设置

```bash
# 进入工作空间
cd u:\项目 大三下\vm_share\data\learnarm_ws

# 构建工作空间
colcon build

# 设置环境
source install/setup.bash
```

### 2. 启动机械臂控制

#### 基础控制启动
```bash
ros2 launch arm1 robot_arm_ros2_control_launch.py
```

#### Action控制启动
```bash
ros2 launch arm1 robot_arm_action_ros2_control_launch.py
```

#### 夹爪控制启动
```bash
ros2 launch arm1 robot_arm_hand_ros2_control_launch.py
```

### 3. 运动规划演示

#### 基础运动规划
```bash
ros2 launch motion_api motion_api.launch.py
```

#### 抓取方块演示
```bash
ros2 launch motion_api pick_block.launch.py
```

### 4. MoveIt完整演示

#### 基础演示
```bash
ros2 launch robot_arm_config demo.launch.py
```

#### 完整演示
```bash
ros2 launch robot_arm_config full_demo.launch.py
```

#### Gazebo仿真
```bash
ros2 launch robot_arm_config gazebo.launch.py
```

#### RViz可视化
```bash
ros2 launch robot_arm_config moveit_rviz.launch.py
```

## 控制器配置

### arm_controller
控制机械臂的6个主要关节（joint1-joint6），使用关节轨迹控制器。

### hand_controller
控制夹爪关节（hand_right_joint），用于抓取和释放操作。

### joint_state_broadcaster
广播所有关节的状态信息，用于RViz可视化和运动规划。

## 开发和测试

### 运行测试脚本

#### Action控制测试
```bash
ros2 run arm1 test_arm_action
```

#### 夹爪控制测试
```bash
ros2 run arm1 test_arm_hand
```

#### 状态发布器测试
```bash
ros2 run arm1 test_arm_publisher
```

### 运动规划测试

#### 基础运动规划测试
```bash
ros2 run motion_api motion_api_test
```

#### 抓取放置测试
```bash
ros2 run motion_api pick_drop
```

#### 玫瑰抓取测试
```bash
ros2 run motion_api pick_rose_drop
```

## 技术栈

- **ROS 2**: Humble
- **编程语言**: Python 3.12
- **运动规划**: MoveIt2 / MoveItPy
- **仿真**: Gazebo
- **可视化**: RViz2
- **控制框架**: ros2_control
- **构建系统**: colcon, ament_cmake, ament_python

## 项目特点

1. **模块化设计**: 将机械臂控制、运动规划和配置分离为独立包
2. **完整的控制链**: 从底层硬件接口到高层运动规划
3. **仿真支持**: 集成Gazebo仿真环境
4. **可视化工具**: 提供RViz配置用于实时监控
5. **多种控制方式**: 支持Action、Publisher等多种控制接口
6. **MoveIt集成**: 完整的运动规划和碰撞检测功能

## 维护者

- **主要维护者**: mccharley (brucelin92@163.com)
- **许可证**: MIT License

## 相关链接

- [MoveIt2 官方文档](http://moveit.ros.org/)
- [MoveIt2 GitHub](https://github.com/moveit/moveit2)
- [ROS 2 文档](https://docs.ros.org/en/rolling/)

## 注意事项

1. 首次使用前需要运行 `colcon build` 构建工作空间
2. 每次修改代码后需要重新构建
3. 启动前确保已正确设置环境变量
4. Gazebo仿真需要额外的依赖包
5. 控制器配置需要根据实际硬件进行调整

## 未来扩展

- 添加更多运动规划算法
- 支持视觉伺服
- 集成力/力矩传感器
- 添加碰撞检测和避障功能
- 支持多机器人协作