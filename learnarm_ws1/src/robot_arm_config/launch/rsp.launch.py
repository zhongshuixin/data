"""Robot State Publisher 启动

- 构建 MoveIt 配置后生成 RSP 启动描述
- 发布 TF 与 `/robot_description`，为 MoveIt/RViz 提供模型状态
"""
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_rsp_launch


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder("arm", package_name="robot_arm_config").to_moveit_configs()
    return generate_rsp_launch(moveit_config)
