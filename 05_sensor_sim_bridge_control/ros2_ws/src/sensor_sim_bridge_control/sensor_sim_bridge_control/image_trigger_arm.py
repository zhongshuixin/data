"""
图像触发机械臂指令发布节点.

功能概览：
- 订阅相机图像话题（sensor_msgs/msg/Image）
- 当满足触发条件时，向控制话题发布一条关节目标（std_msgs/msg/Float64MultiArray）

用途：
- 教学演示“传感器输入 -> 规则触发 -> 控制输出”的最小闭环
- 不做任何图像识别/AI 推理，仅用“收到图像”作为触发事件

参数（可通过 ros2 param set 修改）：
- image_topic：订阅的图像话题（默认 /camera/image_raw）
- command_topic：发布控制指令的话题（默认 /arm_forward_controller/commands）
- target_positions：要发布的关节目标数组（通常 6 个关节）
- one_shot：是否只触发一次（默认 True）
- cooldown_sec：两次发布之间的冷却时间（秒）
- enabled：是否启用触发（默认 True）

服务：
- ~/reset（std_srvs/srv/Trigger）：清空 one_shot 触发状态，允许再次发布
- ~/enable（std_srvs/srv/SetBool）：启用/禁用触发
"""

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import (
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
    qos_profile_sensor_data,
)
from sensor_msgs.msg import Image
from std_msgs.msg import Float64MultiArray
from std_srvs.srv import SetBool, Trigger


class ImageTriggerArm(Node):
    def __init__(self):
        super().__init__("image_trigger_arm")

        # 订阅图像输入与发布控制输出的 ROS 话题名。
        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("command_topic", "/arm_forward_controller/commands")
        # 目标关节位置（示例：6 轴机械臂）。
        self.declare_parameter(
            "target_positions", [0.0, -1.0, 1.2, -1.2, 0.0, 0.0]
        )
        # one_shot=true：收到第一帧图像后只发布一次（常用于演示）。
        self.declare_parameter("one_shot", True)
        # 冷却时间：用于限制发布频率（秒）。
        self.declare_parameter("cooldown_sec", 0.0)
        # enabled=false：禁用触发逻辑（仍会保持订阅/发布器存在）。
        self.declare_parameter("enabled", True)

        self._sent_once = False
        self._last_sent_ns: int | None = None

        # 控制指令 QoS：使用 RELIABLE，确保下游控制器更不容易丢指令。
        command_qos = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=QoSReliabilityPolicy.RELIABLE,
        )

        # 发布器：向 command_topic 发布 Float64MultiArray。
        self._publisher = self.create_publisher(
            Float64MultiArray,
            self.get_parameter("command_topic").value,
            command_qos,
        )

        # 订阅器：相机数据属于典型传感器流，采用 qos_profile_sensor_data（Best Effort）。
        self._subscription = self.create_subscription(
            Image,
            self.get_parameter("image_topic").value,
            self._on_image,
            qos_profile_sensor_data,
        )

        # 服务：用于重置触发状态 / 启用禁用触发。
        self._reset_srv = self.create_service(Trigger, "~/reset", self._on_reset)
        self._enable_srv = self.create_service(SetBool, "~/enable", self._on_enable)

    def _on_enable(self, request: SetBool.Request, response: SetBool.Response):
        # 将 enabled 参数更新为请求值（True/False）。
        self.set_parameters(
            [Parameter("enabled", Parameter.Type.BOOL, bool(request.data))]
        )
        response.success = True
        response.message = "enabled=true" if request.data else "enabled=false"
        return response

    def _on_reset(self, request: Trigger.Request, response: Trigger.Response):
        # 清除 one_shot 状态与上一次发送时间，使下一帧图像可以再次触发发布。
        self._sent_once = False
        self._last_sent_ns = None
        response.success = True
        response.message = "reset ok"
        return response

    def _on_image(self, msg: Image):
        # 说明：msg 本身未被解析，这里只把“收到图像”当作触发事件。
        if not self.get_parameter("enabled").value:
            return

        if self.get_parameter("one_shot").value and self._sent_once:
            return

        cooldown_ns = int(float(self.get_parameter("cooldown_sec").value) * 1e9)
        now_ns = self.get_clock().now().nanoseconds

        if self._last_sent_ns is not None and cooldown_ns > 0:
            if now_ns - self._last_sent_ns < cooldown_ns:
                return

        target_positions = list(self.get_parameter("target_positions").value)
        if len(target_positions) == 0:
            self.get_logger().error("target_positions is empty, skip publish.")
            return

        # 发布控制指令：将 target_positions 填入 Float64MultiArray。
        cmd = Float64MultiArray()
        cmd.data = target_positions
        self._publisher.publish(cmd)
        self._last_sent_ns = now_ns
        self._sent_once = True
        self.get_logger().info(f"Published {len(cmd.data)} joint positions.")


def main(args=None):
    rclpy.init(args=args)
    node = ImageTriggerArm()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
