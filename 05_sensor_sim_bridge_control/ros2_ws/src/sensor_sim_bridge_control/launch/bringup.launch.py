"""
一键启动：Gazebo 相机仿真 + Gazebo→ROS2 桥接 + 图像触发控制节点.

启动内容：
- ign gazebo：运行 worlds/sorting_demo.world（内含 camera sensor）
- ros_gz_bridge/parameter_bridge：
  - /sim/camera/rgb -> /camera/image_raw
  - /sim/camera/camera_info -> /camera/camera_info
- sensor_sim_bridge_control/image_trigger_arm：
  - 订阅 /camera/image_raw
  - 收到图像后向 /arm_forward_controller/commands 发布一次关节目标（默认 one_shot）

常见问题与对应参数：
- Gazebo 消息类型不同（ignition.msgs vs gz.msgs）：
  - gz_image_msg_type / gz_camera_info_msg_type 可覆盖
- 想改 ROS2 侧输出话题名：
  - image_topic / camera_info_topic 可覆盖
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # 全局开关：是否使用 /clock（仿真时间）。
    use_sim_time = LaunchConfiguration("use_sim_time")
    # world 文件路径（默认指向包内 worlds/sorting_demo.world）。
    world = LaunchConfiguration("world")
    # Gazebo 启动命令与子命令（默认：ign gazebo）。
    gazebo_cmd = LaunchConfiguration("gazebo_cmd")
    gazebo_subcmd = LaunchConfiguration("gazebo_subcmd")
    # 强制软件渲染开关（无 GPU 或驱动问题时常用）。
    libgl_always_software = LaunchConfiguration("libgl_always_software")

    # ROS 侧话题名：桥接后的图像与相机内参输出位置。
    image_topic = LaunchConfiguration("image_topic")
    camera_info_topic = LaunchConfiguration("camera_info_topic")
    # ROS 侧控制话题名：image_trigger_arm 节点发布关节指令的位置。
    command_topic = LaunchConfiguration("command_topic")
    # Gazebo Transport 消息类型（不同版本/发行版可能是 ignition.msgs.* 或 gz.msgs.*）。
    gz_image_msg_type = LaunchConfiguration("gz_image_msg_type")
    gz_camera_info_msg_type = LaunchConfiguration("gz_camera_info_msg_type")

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("libgl_always_software", default_value="1"),
            DeclareLaunchArgument(
                "world",
                default_value=PathJoinSubstitution(
                    [
                        FindPackageShare("sensor_sim_bridge_control"),
                        "worlds",
                        "sorting_demo.world",
                    ]
                ),
            ),
            DeclareLaunchArgument("gazebo_cmd", default_value="ign"),
            DeclareLaunchArgument("gazebo_subcmd", default_value="gazebo"),
            DeclareLaunchArgument("image_topic", default_value="/camera/image_raw"),
            DeclareLaunchArgument(
                "camera_info_topic", default_value="/camera/camera_info"
            ),
            DeclareLaunchArgument(
                "command_topic", default_value="/arm_forward_controller/commands"
            ),
            DeclareLaunchArgument(
                "gz_image_msg_type",
                default_value="ignition.msgs.Image",
            ),
            DeclareLaunchArgument(
                "gz_camera_info_msg_type",
                default_value="ignition.msgs.CameraInfo",
            ),
            SetEnvironmentVariable(name="LIBGL_ALWAYS_SOFTWARE", value=libgl_always_software),
            ExecuteProcess(
                # -r：启动即运行（无需在 GUI 点 Play）
                # -v 4：输出更详细日志，便于排查资源加载与传感器发布问题
                cmd=[gazebo_cmd, gazebo_subcmd, "-r", "-v", "4", world],
                output="screen",
            ),
            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                name="camera_bridge",
                output="screen",
                arguments=[
                    # parameter_bridge 的参数是“单个字符串规则”：
                    # <gz_topic>@<ros_type>[<gz_type>
                    # 这里用 PythonExpression 在运行时拼接出完整字符串，避免把参数拆成多个片段。
                    PythonExpression(
                        [
                            "'/sim/camera/rgb@sensor_msgs/msg/Image[' + '",
                            gz_image_msg_type,
                            "'",
                        ]
                    ),
                    PythonExpression(
                        [
                            "'/sim/camera/camera_info@sensor_msgs/msg/CameraInfo[' + '",
                            gz_camera_info_msg_type,
                            "'",
                        ]
                    ),
                ],
                parameters=[{"use_sim_time": ParameterValue(use_sim_time, value_type=bool)}],
                remappings=[
                    # 将 bridge 输出的 ROS 话题重映射到用户自定义名称（默认 /camera/*）。
                    ("/sim/camera/rgb", image_topic),
                    ("/sim/camera/camera_info", camera_info_topic),
                ],
            ),
            Node(
                package="sensor_sim_bridge_control",
                executable="image_trigger_arm",
                name="image_trigger_arm",
                output="screen",
                parameters=[
                    {"use_sim_time": ParameterValue(use_sim_time, value_type=bool)},
                    {"image_topic": image_topic},
                    {"command_topic": command_topic},
                ],
            ),
        ]
    )
