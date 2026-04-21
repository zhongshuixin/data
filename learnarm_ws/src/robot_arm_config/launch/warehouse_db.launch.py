"""MoveIt 规划仓库（MongoDB）启动

- 构建 MoveIt 配置
- 启动 `warehouse_ros_mongo` 以持久化场景与轨迹（可选）
"""
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_warehouse_db_launch


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder("arm", package_name="robot_arm_config").to_moveit_configs()
    return generate_warehouse_db_launch(moveit_config)
