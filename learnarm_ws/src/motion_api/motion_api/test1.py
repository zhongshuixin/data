"""MoveItPy 示例：使用预设姿态进行一次规划与执行

- 通过 `MoveItConfigsBuilder.moveit_cpp` 加载 MoveIt 配置
- 使用 SRDF 的 `stand` 作为起点，`ready` 作为终点
- 执行时使用 `arm_controller` 控制器
"""
import time
import rclpy
from rclpy.logging import get_logger
from moveit.core.robot_state import RobotState
from moveit.planning import (
    MoveItPy,
    MultiPipelinePlanRequestParameters,
)
from moveit_configs_utils import MoveItConfigsBuilder
from pathlib import Path

def plan_and_execute(
    robot,
    planning_component,
    logger,
    single_plan_parameters=None,
    multi_plan_parameters=None,
    sleep_time=0.0,
):
    """规划并执行辅助函数"""
    # 进行路径规划
    logger.info("开始规划轨迹")
    if multi_plan_parameters is not None:
        plan_result = planning_component.plan(
            multi_plan_parameters=multi_plan_parameters
        )
    elif single_plan_parameters is not None:
        plan_result = planning_component.plan(
            single_plan_parameters=single_plan_parameters
        )
    else:
        plan_result = planning_component.plan()

    # 执行规划结果
    if plan_result:
        logger.info("开始执行轨迹")
        robot_trajectory = plan_result.trajectory
        robot.execute(robot_trajectory, controllers=['arm_controller'])
    else:
        logger.error("规划失败")

    time.sleep(sleep_time)

if __name__=="__main__":
    # 初始化 MoveItPy
    rclpy.init()
    logger = get_logger("moveit_py.pose_goal")

    # 兼容跨平台路径：packages/motion_api/config/moveit_cpp.yaml
    path = str(Path(__file__).resolve().parents[1] / 'config' / 'moveit_cpp.yaml')
    print(f'moveit cpp config path is: {path}')
    
    moveit_config = (
        MoveItConfigsBuilder(
            robot_name="arm", package_name="robot_arm_config"
        )
        .moveit_cpp(path)
        .to_moveit_configs()
    )
    
    params=moveit_config.to_dict() #节点moveitpy的参数

    # 初始化 MoveItPy 并获取 `arm` 规划组件
    robot = MoveItPy(node_name="moveit_py",config_dict=params)
    logger.info("MoveItPy instance created")
    print(robot)

     # 获取机械臂规划组件
    arm_group = robot.get_planning_component("arm")

     # 设置起始为预定义的stand位置
    arm_group.set_start_state(configuration_name="stand")

    # 设置终点为预定义的ready位置
    arm_group.set_goal_state(configuration_name="ready")

    # 进行路径规划并执行
    plan_and_execute(robot, arm_group, logger, sleep_time=3.0)