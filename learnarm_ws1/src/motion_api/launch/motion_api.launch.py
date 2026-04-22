"""Motion API 全量启动

- 加载 `robot_arm_config` 的 MoveIt 配置，并指定 `motion_api/config/moveit_cpp.yaml`
- 启动 RSP、静态 TF、RViz、ros2_control、控制器 spawner、move_group
- 额外启动 Python 控制节点 `motion_api_test`，演示 MoveItPy 的规划与执行
"""
from moveit_configs_utils import MoveItConfigsBuilder
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch import LaunchDescription


def generate_launch_description():
    packagepath = get_package_share_directory('robot_arm_config')  
    print(packagepath)
  
    # Load the robot configuration
    moveit_config = MoveItConfigsBuilder("arm", package_name="robot_arm_config").moveit_cpp( 
            file_path=get_package_share_directory("motion_api")+ "/config/moveit_cpp.yaml"
        ).to_moveit_configs()

    # 发布机械臂状态
    robot_desc_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="both",
        parameters=[moveit_config.robot_description],
    )

    # Static TF 发布机械臂虚拟关节坐标系
    static_tf_node = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="static_transform_publisher",
        output="log",
        arguments=["--frame-id", "world", "--child-frame-id", "base_link"],
    )

    # Launch RViz
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

    # ros2_control 控制器管理器节点
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


    # MoveIt 核心 move_group 服务
    move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=[moveit_config.to_dict()],
    )

    # 启动自定义 MoveIt2 Python 控制节点（入口脚本：setup.py console_scripts）
    moveit_py_node = Node(
        name="moveit_py",
        package="motion_api",
        executable="motion_api_test",
        output="both",
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
            moveit_py_node
        ])