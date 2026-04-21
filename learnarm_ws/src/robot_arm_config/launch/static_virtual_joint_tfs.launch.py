"""静态虚拟关节 TF 发布

- 为 SRDF 中定义的 `virtual_joint`（world→base_link）发布静态 TF
- 便于在没有真实移动平台时固定参考系
"""
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_static_virtual_joint_tfs_launch


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder("arm", package_name="robot_arm_config").to_moveit_configs()
    return generate_static_virtual_joint_tfs_launch(moveit_config)
