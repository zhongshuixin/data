import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from builtin_interfaces.msg import Duration

class TrajectoryTestNode(Node):

    def __init__(self):
        super().__init__('trajectory_test_node')
        self.action_client = ActionClient(self, FollowJointTrajectory, '/arm_controller/follow_joint_trajectory') 
        ### /joint_trajectory_controller 是yaml文件里配置的控制器名称，要一致
        self.common_goal_accepted = False
        self.common_resultcode = None
        self.common_action_result_code = FollowJointTrajectory.Result.SUCCESSFUL

    def send_goal(self):
        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.goal_time_tolerance = Duration(sec=1)
        # 定义多个关节的名称
        goal_msg.trajectory.joint_names = ["joint1", "joint2", "joint3","joint4","joint5","joint6"]

        # 定义轨迹点
        points = []

        # 轨迹点 1：初始位置
        point1 = JointTrajectoryPoint()
        point1.time_from_start = Duration(sec=3)  # 轨迹开始时间
        point1.positions = [0.0, 0.0, 1.0,0.0,1.0,0.0]  # 三个关节的位置
        points.append(point1)

        # 轨迹点 2：1秒后移动到指定位置
        point2 = JointTrajectoryPoint()
        point2.time_from_start = Duration(sec=6)
        point2.positions = [0.0, 0.0, 0.0,0.0,0.0,0.0]  # joint_1 到 1.0，joint_2 到 0.5，joint_3 到 -0.5
        points.append(point2)

        # # 轨迹点 3：2秒后达到另一个目标
        # point3 = JointTrajectoryPoint()
        # point3.time_from_start = Duration(sec=2)
        # point3.positions = [2.0, 2.0, -1.0,0.0]  # 三个关节的新位置        points.append(point3)

        goal_msg.trajectory.points = points

        self.action_client.wait_for_server()
        self.send_goal_future = self.action_client.send_goal_async(goal_msg, feedback_callback=self.feedback_callback)
        self.send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('Goal rejected')
            return

        self.get_logger().info('Goal accepted')
        self.get_result_future = goal_handle.get_result_async()
        self.get_result_future.add_done_callback(self.result_callback)

    def result_callback(self, future):
        result = future.result().result
        self.common_resultcode = result.error_code
        if result.error_code == FollowJointTrajectory.Result.SUCCESSFUL:
            self.get_logger().info('SUCCEEDED result code')
        elif result.error_code == FollowJointTrajectory.Result.ABORTED:
            self.get_logger().info('Goal was aborted')
        elif result.error_code == FollowJointTrajectory.Result.CANCELED:
            self.get_logger().info('Goal was canceled')
        else:
            self.get_logger().info('Unknown result code')

    def feedback_callback(self, feedback):
        self.get_logger().info('Feedback received:')
        self.get_logger().info(f'desired.positions: {feedback.feedback.desired.positions[0]}')
        self.get_logger().info(f'desired.velocities: {feedback.feedback.desired.velocities[0]}')
       
def main(args=None):
    rclpy.init(args=args)
    node = TrajectoryTestNode()
    node.send_goal()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()