import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

class GripperTestNode(Node):
    def __init__(self):
        super().__init__('gripper_test_node')
        self.publisher = self.create_publisher(Float64MultiArray, '/hand_controller/commands', 10)
        ###/hand_controller 是yaml文件里配置的控制器名称,要和yaml文件里一致
        self.get_logger().info('node created')
        self.t1=self.create_timer(1.0,self.move)
        self.value=0.05

    def move(self):
        commands = Float64MultiArray()
        if self.value==0:
            self.value=0.05
        else:
            self.value=0
        commands.data = [self.value]
        self.publisher.publish(commands)
def main(args=None):
    rclpy.init(args=args)
    node = GripperTestNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
if __name__ == '__main__':
    main()