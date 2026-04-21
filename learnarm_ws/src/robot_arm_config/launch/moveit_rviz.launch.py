"""MoveIt RViz 可视化启动

- 构建 MoveIt 配置
- 启动 RViz 并加载 MoveIt 的显示与交互面板
"""
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_moveit_rviz_launch


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder("arm", package_name="robot_arm_config").to_moveit_configs()
    return generate_moveit_rviz_launch(moveit_config)
