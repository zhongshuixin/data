"""MoveItPy 示例：末端位姿目标规划与执行

- 设置末端在 `base_link` 坐标系下的可达位姿，使用单位四元数
- 执行前等待控制器服务就绪，失败时回退到 `ready`
"""
import time
import rclpy
from rclpy.logging import get_logger
from rclpy.node import Node
from rclpy.action import ActionClient
from moveit.core.robot_state import RobotState
from moveit.planning import (
    MoveItPy,
    MultiPipelinePlanRequestParameters,
)
from moveit_configs_utils import MoveItConfigsBuilder
from control_msgs.action import FollowJointTrajectory
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

    # get arm group from MoveItPy instance
    arm_group = robot.get_planning_component("arm")

    # 设置机械臂起始位置为当前状态位置
    arm_group.set_start_state_to_current_state()

    # 等待控制器 action server
    waiter_node = Node('arm_controller_waiter')
    arm_action_client = ActionClient(waiter_node, FollowJointTrajectory, '/arm_controller/follow_joint_trajectory')
    arm_action_client.wait_for_server()
    waiter_node.destroy_node()

    # set pose goal
    from geometry_msgs.msg import PoseStamped

    pose_goal = PoseStamped()
    pose_goal.header.frame_id = "base_link"  #表示这个位姿是在哪个参考坐标系下定义的。通常是 机器人底座 或世界坐标系。
    pose_goal.pose.orientation.x = 0.0
    pose_goal.pose.orientation.y = 0.0
    pose_goal.pose.orientation.z = 0.0
    pose_goal.pose.orientation.w = 1.0

    pose_goal.pose.position.x = 0.35
    pose_goal.pose.position.y = 0.0
    pose_goal.pose.position.z = 0.25
    #设置目标位置为指定的直角坐标系位置
    arm_group.set_goal_state(pose_stamped_msg=pose_goal, pose_link="gripper_base_link")  #表示你希望最终到达目标位姿的末端执行器链接名称。

    # 进行路径规划并执行；失败则回退到 SRDF ready
    plan_result = arm_group.plan()
    if plan_result:
        robot_trajectory = plan_result.trajectory
        robot.execute(robot_trajectory, controllers=['arm_controller'])
        time.sleep(3.0)
    else:
        arm_group.set_goal_state(configuration_name="ready")
        plan_and_execute(robot, arm_group, logger, sleep_time=3.0)
    rclpy.shutdown()
