"""ros2_control 控制器加载启动

- 构建 MoveIt 配置
- 生成用于在运行时向 `controller_manager` 插入各控制器的启动描述
"""
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_spawn_controllers_launch


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder("arm", package_name="robot_arm_config").to_moveit_configs()
    return generate_spawn_controllers_launch(moveit_config)
