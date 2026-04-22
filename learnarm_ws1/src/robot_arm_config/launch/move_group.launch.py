"""MoveGroup 核心服务启动

- 构建并加载 MoveIt 配置
- 启动 `move_group`，提供规划与执行服务接口
"""
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_move_group_launch


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder("arm", package_name="robot_arm_config").to_moveit_configs()
    return generate_move_group_launch(moveit_config)
