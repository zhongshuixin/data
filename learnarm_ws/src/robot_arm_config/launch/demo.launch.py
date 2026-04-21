"""MoveIt Demo 启动文件

- 使用 `MoveItConfigsBuilder` 基于本包 `robot_arm_config` 构建 MoveIt 配置
- 运行演示模式（含 RViz + MoveGroup），便于快速测试规划与交互
"""
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_demo_launch


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder("arm", package_name="robot_arm_config").to_moveit_configs()
    return generate_demo_launch(moveit_config)
