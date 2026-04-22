from launch import LaunchDescription
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch.actions import TimerAction

packagepath = get_package_share_directory('arm1')
path=packagepath+'/urdf/robot_arm_ros2_controller.urdf'
robot_desc=open(path).read()

def generate_launch_description():
    robot_desc_node=Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='both',
        parameters=[
            {'use_sim_time': True},
            {'robot_description': robot_desc},
        ]
    )
    rviz_node=Node(
        package='rviz2',
        executable='rviz2',
        name='rviz',
        arguments=[ '-d', packagepath+'/urdf/arm_rviz.rviz'],
       
    )
    controller_manager_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[packagepath+'/config/arm_controllers.yaml'],
        name='controller_manager',
        output="both",
    )
    controllers_node=Node(
            package="controller_manager",
            executable="spawner.py",
            arguments=['arm_controller', 'hand_controller', 'joint_state_broadcaster'],
            output="screen",
            name='controllers',
        )

    arm_action_node=Node(
        package="arm1",
        executable="test_arm_action",
    )
    
    return LaunchDescription([
        robot_desc_node,
        rviz_node,
        controller_manager_node,
        controllers_node,
        TimerAction(
            period=5.0,  # 延迟5秒
            actions=[arm_action_node]
        ),
    ])