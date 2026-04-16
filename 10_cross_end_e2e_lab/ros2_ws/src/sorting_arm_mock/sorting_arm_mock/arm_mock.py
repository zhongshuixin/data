import json
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


@dataclass(frozen=True)
class EnvelopeError:
    # Envelope 校验失败时的“最小错误四元组”：
    # - code/message：给前端提示与日志聚合用
    # - field：精确到字段路径，便于跨端快速定位格式问题
    code: str
    message: str
    field: Optional[str] = None


def _is_dict(x: Any) -> bool:
    return isinstance(x, dict)


def _ms_now() -> int:
    # 统一毫秒时间戳：与 Web 端 ts_ms 字段口径一致
    return int(time.time() * 1000)


def _make_id(prefix: str) -> str:
    # 生成课堂可读的 id（用于 trace_id/msg_id）：
    # - prefix: 'T'（trace） / 'M'（msg）
    # - 形态：<prefix>-YYYYMMDD-xxxxxx
    ts_ms = _ms_now()
    rand = f"{random.randrange(0, 16**6):06x}"
    day = time.localtime(ts_ms / 1000.0)
    y = f"{day.tm_year:04d}"
    m = f"{day.tm_mon:02d}"
    d = f"{day.tm_mday:02d}"
    return f"{prefix}-{y}{m}{d}-{rand}"


def validate_envelope(input_obj: Any) -> Tuple[bool, Any]:
    # 与 Web 侧 validateEnvelope() 保持同一最小校验口径：
    # - 不做 payload 内部业务字段强校验（那属于业务层），但保证 Envelope 的必填字段齐全且类型正确
    # - 这样跨端联调时，“字段缺失/类型漂移”能在第一时间暴露出来
    if not _is_dict(input_obj):
        return False, EnvelopeError(code="BAD_BODY", message="body must be object")

    required_str = ("schema_version", "trace_id", "msg_id", "source", "event")
    for f in required_str:
        v = input_obj.get(f)
        if not isinstance(v, str) or not v:
            return False, EnvelopeError(code="BAD_FIELD", message=f"{f} must be non-empty string", field=f)

    ts_ms = input_obj.get("ts_ms")
    if not isinstance(ts_ms, (int, float)) or not (ts_ms == ts_ms):
        return False, EnvelopeError(code="BAD_FIELD_TYPE", message="ts_ms must be finite number", field="ts_ms")

    payload = input_obj.get("payload")
    if not _is_dict(payload):
        return False, EnvelopeError(code="BAD_FIELD_TYPE", message="payload must be object", field="payload")

    return True, input_obj


def make_envelope(
    *,
    trace_id: str,
    source: str,
    target: str,
    topic: str,
    event: str,
    payload: Dict[str, Any],
    schema_version: str = "1.0.0",
    content_type: str = "application/json",
) -> Dict[str, Any]:
    # 统一 Envelope 构造函数：避免各处手写字段导致漂移
    # - trace_id：跨端贯穿一次闭环（请求→执行→回执）
    # - msg_id：每条消息唯一
    # - event：业务语义（比 topic 更稳定、更便于测试用例组织）
    return {
        "schema_version": schema_version,
        "trace_id": trace_id,
        "msg_id": _make_id("M"),
        "source": source,
        "target": target,
        "topic": topic,
        "event": event,
        "ts_ms": _ms_now(),
        "content_type": content_type,
        "payload": payload,
    }


def _safe_json_dumps(obj: Any) -> str:
    # ensure_ascii=False：允许中文 message（便于课堂展示）
    # separators：去掉多余空格，减少 ws/rosbridge 传输体积
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class SortingArmMockNode(Node):
    def __init__(self) -> None:
        super().__init__("sorting_arm_mock")

        # 控制面（cmd/status）话题：统一用 std_msgs/msg/String 承载 Envelope JSON 字符串
        self.cmd_topic = "/sorting_arm/cmd"
        self.status_topic = "/sorting_arm/status"

        # /sorting_arm/status：回执发布端
        self.pub_status = self.create_publisher(String, self.status_topic, 10)
        # /sorting_arm/cmd：命令订阅端（Web 下发的 Envelope<ArmCommand>）
        self.sub_cmd = self.create_subscription(String, self.cmd_topic, self.on_cmd, 10)

        # 数据面三路模拟话题：用于保证 dashboard 页面“可复现、可验收”
        self.pub_device_state = self.create_publisher(String, "/device/state_json", 10)
        self.pub_params = self.create_publisher(String, "/device/params_json", 10)
        self.pub_detections = self.create_publisher(String, "/vision/detections_json", 10)

        # 模拟设备内部状态（用于 /device/state_json）
        self._battery = 100.0
        self._temperature = 36.5
        self._mode = "idle"

        # 定时发布模拟数据：频率按“课堂可视化效果”设置
        # - state: 2 Hz（0.5s）
        # - params: 1 Hz（1.0s）
        # - detections: 5 Hz（0.2s）
        self.create_timer(0.5, self._tick_device_state)
        self.create_timer(1.0, self._tick_params)
        self.create_timer(0.2, self._tick_detections)

        self.get_logger().info("sorting_arm_mock started (Envelope JSON over std_msgs/msg/String)")

    def _publish_json_envelope(self, topic: str, env: Dict[str, Any]) -> None:
        # 统一发布函数：topic 不同，但承载逻辑一致（String.data = Envelope JSON 字符串）
        msg = String()
        msg.data = _safe_json_dumps(env)
        if topic == self.status_topic:
            self.pub_status.publish(msg)
        elif topic == "/device/state_json":
            self.pub_device_state.publish(msg)
        elif topic == "/device/params_json":
            self.pub_params.publish(msg)
        elif topic == "/vision/detections_json":
            self.pub_detections.publish(msg)

    def _reject(self, *, trace_id: str, field: Optional[str], code: str, message: str) -> None:
        # 控制面“错误回执”统一格式：Envelope< {ok,code,message,field} >
        # 关键点：trace_id 必须回传，才能把“请求与错误”串起来定位
        payload = {"ok": False, "code": code, "message": message, "field": field}
        env = make_envelope(
            trace_id=trace_id,
            source="ros2",
            target="web",
            topic=self.status_topic,
            event="arm.command.reject",
            payload=payload,
        )
        self._publish_json_envelope(self.status_topic, env)

    def on_cmd(self, msg: String) -> None:
        # 处理 Web 下发的 /sorting_arm/cmd：
        # 1) 解析 String.data 为 JSON
        # 2) 校验 Envelope 外壳（字段/类型）
        # 3) 校验最小业务字段（cmd_id/device_id/action）
        # 4) 发布 /sorting_arm/status（Envelope<ArmStatus>）
        try:
            root = json.loads(msg.data)
        except Exception:
            self._reject(trace_id=_make_id("T"), field=None, code="BAD_BODY", message="cmd.data is not valid JSON")
            return

        ok, result = validate_envelope(root)
        if not ok:
            err: EnvelopeError = result
            self._reject(trace_id=root.get("trace_id", _make_id("T")), field=err.field, code=err.code, message=err.message)
            return

        env: Dict[str, Any] = result
        trace_id = str(env["trace_id"])
        payload = env["payload"]

        # 课堂闭环匹配关键：cmd_id（请求） ↔ last_cmd_id（回执）
        cmd_id = payload.get("cmd_id")
        device_id = payload.get("device_id", "arm_01")
        action = payload.get("action")

        if not isinstance(cmd_id, str) or not cmd_id:
            self._reject(trace_id=trace_id, field="payload.cmd_id", code="BAD_FIELD", message="payload.cmd_id must be non-empty string")
            return

        if not isinstance(device_id, str) or not device_id:
            self._reject(trace_id=trace_id, field="payload.device_id", code="BAD_FIELD", message="payload.device_id must be non-empty string")
            return

        if not isinstance(action, str) or not action:
            self._reject(trace_id=trace_id, field="payload.action", code="BAD_FIELD", message="payload.action must be non-empty string")
            return

        # 这里是 mock 的“执行模型”：
        # - 收到指令就立即回传结果（便于课堂演示）
        # - 真实设备应在执行结束/状态变化时回传，并携带更丰富的 state/progress 等字段
        self._mode = "running"

        status_payload: Dict[str, Any] = {
            "device_type": "arm",
            "device_id": device_id,
            "state": "idle" if action != "e_stop" else "estop",
            "last_cmd_id": cmd_id,
            "ok": True,
            "code": "OK",
            "message": "mock status",
            "detail": {"received_action": action, "received_event": env.get("event")},
            "ts_ms": _ms_now(),
        }
        status_env = make_envelope(
            trace_id=trace_id,
            source="ros2",
            target="web",
            topic=self.status_topic,
            event="arm.command.result",
            payload=status_payload,
        )
        self._publish_json_envelope(self.status_topic, status_env)
        self._mode = "idle"

    def _tick_device_state(self) -> None:
        # 模拟设备状态（dashboard 用）：
        # - battery/temperature/报警等级：用于曲线与状态卡片
        self._battery = max(0.0, self._battery - random.random() * 0.2)
        self._temperature = 35.0 + random.random() * 8.0
        alarm_level = "OK" if self._battery > 20 else ("WARN" if self._battery > 10 else "ERROR")

        payload: Dict[str, Any] = {
            "device_id": "arm_01",
            "online": True,
            "mode": self._mode,
            "battery": round(self._battery, 2),
            "temperature": round(self._temperature, 2),
            "alarm_level": alarm_level,
            "stamp_ms": _ms_now(),
        }
        env = make_envelope(
            trace_id=_make_id("T"),
            source="ros2",
            target="web",
            topic="/device/state_json",
            event="device.state",
            payload=payload,
        )
        self._publish_json_envelope("/device/state_json", env)

    def _tick_params(self) -> None:
        # 模拟参数快照（dashboard 用）：params 允许嵌套对象，验证前端“异常/复杂数据兼容”
        payload: Dict[str, Any] = {
            "stamp_ms": _ms_now(),
            "params": {
                "kp": 1.2,
                "ki": 0.02,
                "kd": 0.1,
                "max_speed": 0.8,
                "debug": {"enabled": True},
            },
        }
        env = make_envelope(
            trace_id=_make_id("T"),
            source="ros2",
            target="web",
            topic="/device/params_json",
            event="device.params",
            payload=payload,
        )
        self._publish_json_envelope("/device/params_json", env)

    def _tick_detections(self) -> None:
        # 模拟视觉检测（dashboard 用）：detections 数量随机，演示“空数组/多目标”的 UI 变化
        detections = []
        for _ in range(random.randint(0, 3)):
            label = random.choice(["person", "forklift", "box", "pallet"])
            score = round(0.6 + random.random() * 0.4, 2)
            bbox = {"x": random.randint(0, 300), "y": random.randint(0, 200), "w": random.randint(20, 160), "h": random.randint(20, 160)}
            detections.append({"label": label, "score": score, "bbox": bbox})

        payload: Dict[str, Any] = {
            "frame_id": "camera_front",
            "stamp_ms": _ms_now(),
            "detections": detections,
        }
        env = make_envelope(
            trace_id=_make_id("T"),
            source="ros2",
            target="web",
            topic="/vision/detections_json",
            event="vision.detections",
            payload=payload,
        )
        self._publish_json_envelope("/vision/detections_json", env)


def main() -> None:
    # ROS2 Python 节点标准入口：init → spin → destroy → shutdown
    rclpy.init()
    node = SortingArmMockNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
