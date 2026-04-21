"""MoveItPy 示例：设定安全关节角目标并执行

- 避免随机目标导致自碰，直接设置一组可行的关节角
- 失败时回退到 SRDF 的 `ready` 姿态
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

    #########方法一：设置可行的关节角位置（避免随机自碰导致目标无效）
    # 创建RobotState对象
    robot_model = robot.get_robot_model()
    robot_state = RobotState(robot_model)

     # get arm group from MoveItPy instance
    arm_group = robot.get_planning_component("arm")

    # 使用一组已验证的安全关节角
    safe_positions = [0.0, -0.4, -0.79, -0.79, -1.10, 1.55]
    robot_state.set_joint_group_positions('arm', safe_positions)
    logger.info("Set goal state to predefined safe joint positions")
    arm_group.set_goal_state(robot_state=robot_state)

    # 设置机械臂起始位置为当前状态位置
    arm_group.set_start_state_to_current_state()
    # 进行路径规划并执行；若失败则回退到 SRDF 的 ready 姿态
    plan_result = arm_group.plan()
    if plan_result:
        robot_trajectory = plan_result.trajectory
        robot.execute(robot_trajectory, controllers=['arm_controller'])
        time.sleep(3.0)
    else:
        logger.warn("Safe joint goal planning failed, fallback to SRDF 'ready'")
        arm_group.set_goal_state(configuration_name="ready")
        plan_and_execute(robot, arm_group, logger, sleep_time=3.0)

    # ##########方法二：通过关节角设置位置
    # robot_model = robot.get_robot_model()
    # robot_state = RobotState(robot_model)

    # # 指定关节位置，并将其设置为目标状态
    # robot_state.set_joint_group_positions('arm',[0,-0.4,-0.79,-0.79,-1.10,1.55])
    # arm_group.set_goal_state(robot_state=robot_state)

    # # 设置机械臂起始位置为当前状态位置
    # arm_group.set_start_state_to_current_state()

    # # 进行路径规划并执行
    # plan_and_execute(robot, arm_group, logger, sleep_time=3.0)