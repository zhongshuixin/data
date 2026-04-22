"""MoveItPy 机械臂运动规划 Python API 示例

- 展示如何使用 `MoveItPy` 获取规划组件并进行状态切换与执行
- 预设使用 SRDF 中的 `stand` 与 `ready` 姿态进行往返运动
- 注意：若在独立运行而非通过 launch 启动，需确保控制器与 MoveIt 参数已加载
"""
import time
import rclpy
from rclpy.logging import get_logger

# MoveIt Python 库
from moveit.core.robot_state import RobotState
from moveit.planning import (
    MoveItPy,
    MultiPipelinePlanRequestParameters,
)
from moveit_configs_utils import MoveItConfigsBuilder

def plan_and_execute(
    robot,
    planning_component,
    logger,
    single_plan_parameters=None,
    multi_plan_parameters=None,
    sleep_time=0.0,
):
    """规划并执行辅助函数"""
    # plan to goal
    logger.info("Planning trajectory")
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

    # execute the plan
    if plan_result:
        logger.info("Executing plan")
        robot_trajectory = plan_result.trajectory
        # 指定使用机械臂控制器执行轨迹
        robot.execute(robot_trajectory, controllers=['arm_controller'])
    else:
        logger.error("Planning failed")

    time.sleep(sleep_time)


def main():
    rclpy.init()
    logger = get_logger("moveit_py.pose_goal")

    # 初始化 MoveItPy 并获取 `arm` 规划组件
    robot = MoveItPy(node_name="moveit_py")
    arm_group = robot.get_planning_component("arm")
    logger.info("MoveItPy instance created")

    # 使用预设姿态作为规划起点
    arm_group.set_start_state(configuration_name="stand")

    # 使用预设姿态作为规划目标
    arm_group.set_goal_state(configuration_name="ready")

    # 执行规划与执行
    plan_and_execute(robot, arm_group, logger, sleep_time=3.0)
    while True: #循环移动
        # 设置从起点移到终点
        arm_group.set_start_state(configuration_name="ready")
        # 使用预设姿态作为目标
        arm_group.set_goal_state(configuration_name="stand")
        plan_and_execute(robot, arm_group, logger, sleep_time=3.0)

        # 设置从终点移到起点
        arm_group.set_start_state(configuration_name="stand")
        # 使用预设姿态作为目标
        arm_group.set_goal_state(configuration_name="ready")
        plan_and_execute(robot, arm_group, logger, sleep_time=3.0)