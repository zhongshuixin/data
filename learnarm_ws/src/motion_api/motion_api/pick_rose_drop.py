#!/usr/bin/env python3
import time
import rclpy
from rclpy.logging import get_logger
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped

# moveit python library
from moveit.core.robot_state import RobotState
from moveit.planning import MoveItPy
from moveit_configs_utils import MoveItConfigsBuilder

class PickAndPlaceNode(Node):
    def __init__(self):
        super().__init__('pick_and_place_node')
        self.logger = self.get_logger()
        
    def plan_and_execute(self, robot, planning_component, step_name="", sleep_time=3.0):
        """Helper function to plan and execute a motion."""
        try:
            self.logger.info(f"{step_name}: 规划轨迹...")
            
            # 设置规划时间更长以确保找到可行轨迹
            planning_component.planning_time = 10.0
            
            # 尝试规划
            plan_result = planning_component.plan()
            
            if plan_result:
                self.logger.info(f"{step_name}: 执行计划...")
                robot_trajectory = plan_result.trajectory
                robot.execute(robot_trajectory, controllers=[])
                self.logger.info(f"{step_name}: 成功")
                return True
            else:
                self.logger.error(f"{step_name}: 规划失败")
                return False
                
        except Exception as e:
            self.logger.error(f"{step_name}: 错误 - {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
        
        finally:
            time.sleep(sleep_time)

def main():
    
    rclpy.init()
    node = PickAndPlaceNode()
    logger = node.get_logger()

    try:
        logger.info("========== 开始机械臂抓取任务 ==========")
        
        # 给系统更多时间初始化
        logger.info("等待系统初始化...")
        time.sleep(12.0)

        # 创建MoveItPy实例
        logger.info("创建MoveItPy实例...")
        
        # 使用 MoveItConfigsBuilder
        from ament_index_python.packages import get_package_share_directory
        import os
        
        # 获取配置路径
        robot_arm_config_path = get_package_share_directory('robot_arm_config')
        motion_api_path = get_package_share_directory('motion_api')
        
        moveit_config = (MoveItConfigsBuilder("arm", package_name="robot_arm_config")
                        .robot_description('config/arm.gazebo.friction.urdf.xacro')
                        .robot_description_semantic('config/arm.srdf')
                        .moveit_cpp(os.path.join(motion_api_path, "config/moveit_cpp.yaml"))
                        .to_moveit_configs())
        
        robot = MoveItPy(
            node_name="moveit_py",
            config_dict=moveit_config.to_dict()
        )
        
        arm_group = robot.get_planning_component("arm")
        hand_group = robot.get_planning_component('hand')
        logger.info("MoveItPy实例创建成功")
        
        # 等待控制器就绪
        logger.info("等待控制器就绪...")
        time.sleep(15.0)

        # 0. 确保夹爪完全打开
        logger.info("步骤0: 确保夹爪完全打开")
        hand_group.set_start_state_to_current_state()
        hand_group.set_goal_state("open")
        if not node.plan_and_execute(robot, hand_group, "步骤0: 打开夹爪", sleep_time=4.0):
            logger.warning("夹爪打开失败，继续尝试...")

        # 1. 回到初始位置
        logger.info("步骤1: 回到初始位置")
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state("stand")
        node.plan_and_execute(robot, arm_group, "步骤1: 回到初始位置", sleep_time=5.0)

        robot_model = robot.get_robot_model()
        robot_state = RobotState(robot_model)
        
        # ========== 抓取粉色圆柱（位置：x=0.4, y=0.0, z=0.025）==========
        
        # 2. 移动到粉色圆柱上方高位置观察
        logger.info("步骤2: 移动到粉色圆柱上方观察位置")
        # 调整关节角度，保持夹爪垂直向下
        robot_state.set_joint_group_positions('arm', [1.57, 0.0, -0.6, -1.57, 0.0, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤2: 移动到观察位置", sleep_time=6.0)
        
        # 3. 缓慢下降到圆柱上方中等高度
        logger.info("步骤3: 缓慢下降到圆柱上方中等高度")
        robot_state.set_joint_group_positions('arm', [1.57, 0.4, -1.0, -1.3, 0.3, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤3: 下降到中等高度", sleep_time=6.0)
        
        # 4. 微调对准圆柱位置（更精确的位置）
        logger.info("步骤4: 微调对准圆柱位置")
        robot_state.set_joint_group_positions('arm', [1.57, 0.5, -1.2, -1.1, 0.4, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤4: 微调对准", sleep_time=6.0)
        
        # 5. 降低到抓取高度（确保夹爪能包裹住圆柱）
        logger.info("步骤5: 降低到抓取高度")
        robot_state.set_joint_group_positions('arm', [1.57, 0.55, -1.3, -1.0, 0.45, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤5: 抓取高度", sleep_time=8.0)
        
        # 6. 关闭夹爪抓取粉色圆柱（增加闭合时间和力度）
        logger.info("步骤6: 关闭夹爪抓取粉色圆柱")
        hand_group.set_start_state_to_current_state()
        hand_group.set_goal_state("close")
        
        # 执行抓取动作（更长时间确保完全闭合）
        if not node.plan_and_execute(robot, hand_group, "步骤6: 关闭夹爪", sleep_time=10.0):
            logger.warning("夹爪闭合可能不完整，继续尝试...")
        
        # 7. 轻微调整夹爪角度增加抓取力
        logger.info("步骤7: 轻微调整夹爪角度增加抓取力")
        time.sleep(2.0)
        
        # 尝试再次轻微闭合（额外保险）
        hand_group.set_start_state_to_current_state()
        hand_group.set_goal_state("close")
        if node.plan_and_execute(robot, hand_group, "步骤7: 二次夹紧", sleep_time=3.0):
            logger.info("二次夹紧成功")
        
        # 8. 等待夹爪稳定
        logger.info("步骤8: 等待夹爪稳定")
        time.sleep(3.0)
        
        # 9. 非常缓慢地垂直抬起（保持夹爪垂直）
        logger.info("步骤9: 非常缓慢地垂直抬起圆柱")
        # 保持相同姿态，只增加高度
        robot_state.set_joint_group_positions('arm', [1.57, 0.3, -0.9, -1.3, 0.3, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤9: 缓慢垂直抬起", sleep_time=8.0)
        
        # 10. 检查抓取稳定性（小幅移动测试）
        logger.info("步骤10: 检查抓取稳定性")
        robot_state.set_joint_group_positions('arm', [1.57, 0.2, -0.8, -1.4, 0.2, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤10: 稳定性测试", sleep_time=8.0)
        
        # ========== 移动到盒子（位置：x=0.3, y=0.8, z=0.025）==========
        
        # 11. 旋转到盒子方向
        logger.info("步骤11: 旋转到盒子方向")
        robot_state.set_joint_group_positions('arm', [0.0, 0.2, -0.8, -1.4, 0.2, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤11: 旋转方向", sleep_time=6.0)
        
        # 12. 移动到盒子上方
        logger.info("步骤12: 移动到盒子上方")
        robot_state.set_joint_group_positions('arm', [0.0, 0.3, -1.0, -1.2, 0.3, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤12: 盒子正上方", sleep_time=6.0)
        
        # 13. 缓慢下降到放置高度
        logger.info("步骤13: 缓慢下降到放置高度")
        robot_state.set_joint_group_positions('arm', [0.0, 0.4, -1.1, -1.0, 0.4, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤13: 放置高度", sleep_time=8.0)
        
        # 14. 缓慢打开夹爪释放圆柱
        logger.info("步骤14: 缓慢打开夹爪释放圆柱")
        hand_group.set_start_state_to_current_state()
        hand_group.set_goal_state("open")
        node.plan_and_execute(robot, hand_group, "步骤14: 打开夹爪", sleep_time=6.0)
        
        # 15. 等待圆柱稳定放置
        logger.info("步骤15: 等待圆柱稳定放置")
        time.sleep(3.0)
        
        # 16. 抬起夹爪离开盒子
        logger.info("步骤16: 抬起夹爪离开盒子")
        robot_state.set_joint_group_positions('arm', [0.0, 0.3, -1.0, -1.2, 0.3, 1.57])
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state(robot_state=robot_state)
        node.plan_and_execute(robot, arm_group, "步骤16: 抬起离开", sleep_time=5.0)

        # 17. 回到初始位置
        logger.info("步骤17: 回到初始位置")
        arm_group.set_start_state_to_current_state()
        arm_group.set_goal_state("stand")
        node.plan_and_execute(robot, arm_group, "步骤17: 回到初始位置", sleep_time=6.0)

        logger.info('========== 任务完成 ==========')
        
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        logger.info("清理资源...")
        time.sleep(3.0)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()