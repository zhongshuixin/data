#!/usr/bin/python3
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

# 获取当前包的安装地址
packagepath = get_package_share_directory('arm1')
print(packagepath)

# 读取urdf文件
urdfpath = packagepath + '/urdf/robot.urdf'
with open(urdfpath, 'r') as file:
    robot_desc = file.read()

def generate_launch_description():
    robot_desc_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='both',
        parameters=[{'robot_description': robot_desc}]
    )

    # 注意：ROS 2 Jazzy 中包名为 joint_state_publisher_gui
    joint_state_pub_node = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        name='joint_state_publisher_gui'  # 推荐添加节点名
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz',
        arguments=['-d', packagepath + '/urdf/rviz.rviz']
    )

    return LaunchDescription([
        robot_desc_node,
        joint_state_pub_node,
        rviz_node,
    ])