#!/usr/bin/python3
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

# 获取当前包的安装地址
package_path = get_package_share_directory('arm1')
print(f"Package path: {package_path}")

# 读取urdf文件 - 使用更安全的上下文管理器
urdf_path = package_path + '/urdf/robot_arm.urdf'
with open(urdf_path, 'r') as file:
    robot_description = file.read()

def generate_launch_description():
    # 1. 机器人状态发布节点
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description}]
    )

    # 2. 关节状态发布器 GUI (用于交互控制)
    # **重要：ROS 2 Jazzy 中包名为此**
    joint_state_publisher_gui_node = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        name='joint_state_publisher_gui'
    )

    # 3. RViz2 可视化节点
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', package_path + '/urdf/robot_arm.rviz'], # 建议为机械臂创建专属配置文件
        output='screen'
    )

    return LaunchDescription([
        robot_state_publisher_node,
        joint_state_publisher_gui_node,
        rviz_node,
    ])