"""MoveItPy 示例：多规划管线联合规划

- 使用 `ompl_rrtc`、`pilz_lin`、`chomp_planner` 多管线参数联合尝试
- 目标使用 SRDF 的 `ready` 姿态，起点为当前状态
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
    # MoveItPy Setup
    rclpy.init()
    logger = get_logger("moveit_py.pose_goal")

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

    # instantiate MoveItPy instance and get planning component
    robot = MoveItPy(node_name="moveit_py",config_dict=params)
    logger.info("MoveItPy instance created")
    print(robot)

    arm_group = robot.get_planning_component("arm")
    
    # set plan start state to current state
    arm_group.set_start_state_to_current_state()

    # set pose goal with PoseStamped message
    arm_group.set_goal_state(configuration_name="ready")

    # initialise multi-pipeline plan request parameters
    multi_pipeline_plan_request_params = MultiPipelinePlanRequestParameters(
        robot, ["ompl_rrtc", "pilz_lin", "chomp_planner"]
    )

    # plan to goal
    plan_and_execute(
        robot,
        arm_group,
        logger,
        multi_plan_parameters=multi_pipeline_plan_request_params,
        sleep_time=3.0,
    )
