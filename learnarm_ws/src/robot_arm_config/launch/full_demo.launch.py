"""MoveIt + ros2_control 全量演示启动

- 读取本包 `robot_arm_config` 的 MoveIt 配置（URDF/SRDF/IK/规划器等）
- 启动以下组件形成完整演示闭环：
  1) `robot_state_publisher`：发布 `/robot_description` 与 TF
  2) `static_transform_publisher`：发布 world→base_link 的静态 TF
  3) `rviz2`：加载 MoveIt 面板与显示配置 `config/moveit.rviz`
  4) `ros2_control_node`：加载控制器参数 `config/ros2_controllers.yaml`
  5) `spawner`：依次启动 `joint_state_broadcaster`、`arm_controller`、`hand_controller`
  6) `move_group`：MoveIt 规划与执行服务
"""
from moveit_configs_utils import MoveItConfigsBuilder
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch import LaunchDescription

def generate_launch_description():
    packagepath = get_package_share_directory('robot_arm_config')  
    print(packagepath)
  
    # 加载 MoveIt 配置（包含 robot_description / robot_description_semantic 等参数集）
    moveit_config = MoveItConfigsBuilder("arm", package_name="robot_arm_config").to_moveit_configs()

    # 发布机械臂状态：robot_state_publisher 按关节状态生成 TF
    robot_desc_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="both",
        parameters=[moveit_config.robot_description],
    )

    # 静态 TF：发布 world→base_link 的固定坐标关系（对应 SRDF 的 virtual_joint）
    static_tf_node = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="static_transform_publisher",
        output="log",
        arguments=["--frame-id", "world", "--child-frame-id", "base_link"],
    )

    # 启动 RViz：加载 MoveIt 相关参数与预设显示配置
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        output="log",
        arguments=["-d", packagepath+'/config/moveit.rviz'],
        parameters=[
            moveit_config.robot_description,
            moveit_config.robot_description_semantic,
            moveit_config.robot_description_kinematics,
            moveit_config.planning_pipelines,
            moveit_config.joint_limits,
        ],
    )

    # ros2_control 主节点：读取控制器配置，作为控制器管理器
    ros2_control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[packagepath+'/config/ros2_controllers.yaml'],
        output="both",
    )

    # 先启动状态广播器（提供 /joint_states，TF 依赖）
    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=['joint_state_broadcaster'],
        output="screen",
    )
    # 再启动机械臂与夹爪控制器
    controllers_node = Node(
        package="controller_manager",
        executable="spawner",
        arguments=['arm_controller', 'hand_controller'],
        output="screen",
    )

    # MoveIt 核心：move_group 服务节点，提供规划/执行接口
    move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=[moveit_config.to_dict()],
    )

    return LaunchDescription([
            robot_desc_node,
            static_tf_node,
            rviz_node,
            ros2_control_node,
            joint_state_broadcaster_spawner,
            controllers_node,
            move_group_node,
        ])
