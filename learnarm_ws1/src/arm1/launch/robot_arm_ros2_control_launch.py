#!/usr/bin/python3
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
import os

def generate_launch_description():
    package_path = get_package_share_directory('arm1')
    
    # 读取URDF文件
    urdf_path = os.path.join(package_path, 'urdf', 'robot_arm_ros2_controller.urdf')
    with open(urdf_path, 'r') as f:
        robot_description = f.read()

    # 1. 机器人状态发布器
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description}]
    )

    # 2. ros2_control节点 (控制器管理器)
    controller_manager_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[os.path.join(package_path, 'config', 'arm_controllers.yaml')],
        output="screen",
    )

    # 3. 启动各个控制器 (Humble中使用 spawner.py)
    # 注意：Humble中正确的可执行文件名是 `spawner.py`
    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner.py",
        arguments=["joint_state_broadcaster", "-c", "/controller_manager"],
        output="screen",
    )
    
    arm_controller_spawner = Node(
        package="controller_manager",
        executable="spawner.py",
        arguments=["arm_controller", "-c", "/controller_manager"],
        output="screen",
    )
    
    hand_controller_spawner = Node(
        package="controller_manager",
        executable="spawner.py",
        arguments=["hand_controller", "-c", "/controller_manager"],
        output="screen",
    )

    # 4. RViz2 可视化
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", os.path.join(package_path, 'urdf', 'arm_rviz.rviz')],
        output="screen",
    )

    return LaunchDescription([
        robot_state_publisher_node,
        controller_manager_node,
        joint_state_broadcaster_spawner,
        arm_controller_spawner,
        hand_controller_spawner,
        rviz_node,
    ])