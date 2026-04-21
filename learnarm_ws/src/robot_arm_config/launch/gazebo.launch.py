from moveit_configs_utils import MoveItConfigsBuilder
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch import LaunchDescription
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    packagepath = get_package_share_directory('robot_arm_config')  
    print(packagepath)
    controller_ns = LaunchConfiguration('controller_ns')
  
    # 加载 MoveIt 机器人配置
    moveit_config =( MoveItConfigsBuilder("arm", package_name="robot_arm_config")
                    .robot_description('config/arm.gazebo.urdf.xacro')
                    .robot_description_semantic('config/arm.srdf').to_moveit_configs()
    )

    # 启动Gazebo
    gazebo_node = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            get_package_share_directory('ros_gz_sim')+'/launch/gz_sim.launch.py']),
            launch_arguments=[('gz_args','empty.sdf -r --physics-engine gz-physics-bullet-featherstone-plugin')]
    )

    #　将机械臂添加到Gazebo
    robot_to_gazebo_node = Node(
            package='ros_gz_sim',
            executable='create',
            arguments=[ '-string', moveit_config.robot_description['robot_description'], '-x', '0.0', '-y', '0.0', '-z','0.0' ,'-name', 'arm']
        )

    # Clock Bridge
    clock_bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen'
    )

    # 发布机械臂状态
    robot_desc_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="both",
        parameters=[moveit_config.robot_description,
                     {'use_sim_time': True},    #必须使用仿真时间
                     { "publish_frequency":30.0,},
                     ],
    )

    # 启动 RViz 可视化
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
            {'use_sim_time': True},
        ],
    )

    # ros2_control 控制器管理器（由 Gazebo 插件创建，无需单独节点）
    # 使用 gz_ros2_control 时，不需要单独启动 ros2_control_node
    # 控制器管理器由 Gazebo 插件在模型命名空间下创建为 `/arm/controller_manager`

    # 先启动状态广播器（提供 /joint_states，TF 依赖）；延迟以等待 Gazebo 插件初始化
    joint_state_broadcaster_spawner = TimerAction(
        period=5.0,
        actions=[
            # 首选使用模型命名空间下的控制器管理器（例如 /arm/controller_manager）
            Node(
                package="controller_manager",
                executable="spawner",
                arguments=['joint_state_broadcaster', '-c', controller_ns],
                output="screen",
            ),
            # 兼容某些环境默认的根命名空间控制器管理器（/controller_manager）
            Node(
                package="controller_manager",
                executable="spawner",
                arguments=['joint_state_broadcaster', '-c', '/controller_manager'],
                output="screen",
            ),
        ],
    )
    # 再启动机械臂与夹爪控制器；同样延迟
    controllers_node = TimerAction(
        period=6.0,
        actions=[
            Node(
                package="controller_manager",
                executable="spawner",
                arguments=['arm_controller', 'hand_controller', '-c', controller_ns],
                output="screen",
            ),
            Node(
                package="controller_manager",
                executable="spawner",
                arguments=['arm_controller', 'hand_controller', '-c', '/controller_manager'],
                output="screen",
            ),
        ],
    )

    # 启动move_group node/action server
    move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=[moveit_config.to_dict(),
                    {'use_sim_time': True}],
    )

    return LaunchDescription([
            DeclareLaunchArgument(
                'controller_ns',
                default_value='/controller_manager',
                description='ros2_control controller_manager 服务命名空间（Gazebo模型名下通常为 /<model>/controller_manager）'
            ),
            gazebo_node,
            robot_to_gazebo_node,
            clock_bridge_node,
            robot_desc_node,
            rviz_node,
            joint_state_broadcaster_spawner,
            controllers_node,
            move_group_node,
        ])
