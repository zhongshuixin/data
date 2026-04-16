"""
ROS2 端设备控制节点（课堂版）。

核心能力（对应 16 讲义第一课时）：
- 订阅 /sorting_arm/cmd（std_msgs/String），解析 JSON 指令（支持 ArmCommand 与 23 的 Envelope(payload=ArmCommand)）
- 做二次校验与安全门禁（端侧永远不信任上游）
- 调用驱动（课堂用 Mock 驱动；真实设备/仿真可替换为实际 Driver）
- 发布 /sorting_arm/status（std_msgs/String），回执可解释且可追踪（ok/code/message/last_cmd_id）
"""

import json
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def now_ms() -> int:
    # 统一毫秒时间戳，便于跨端联调定位延迟/重放问题
    return int(time.time() * 1000)


@dataclass(frozen=True)
class DeviceCommand:
    # 端侧内部使用的结构化指令对象：解析阶段收敛字段，执行阶段不再直接操作 dict
    cmd_id: str
    scene: str
    device_type: str
    device_id: str
    action: str
    params: dict[str, Any]
    safety: dict[str, Any]
    meta: dict[str, Any]
    ts_ms: int
    trace_id: str | None
    msg_id: str | None
    event: str | None
    topic: str | None


class MockSortingArmDriver:
    # 驱动层替身：课堂阶段不接真实设备，只模拟耗时与错误
    def __init__(self) -> None:
        self._estop = False

    def e_stop(self) -> None:
        self._estop = True

    def reset_estop(self) -> None:
        self._estop = False

    def home(self) -> None:
        self._ensure_not_estop()
        time.sleep(0.3)

    def pick_place(self, from_bin: str, to_bin: str, speed: float) -> None:
        self._ensure_not_estop()
        if speed <= 0 or speed > 1.0:
            raise ValueError("speed must be in (0, 1.0]")
        time.sleep(0.6)

    def stop(self) -> None:
        time.sleep(0.05)

    def _ensure_not_estop(self) -> None:
        if self._estop:
            raise RuntimeError("device is in estop")


class SortingArmControlNode(Node):
    def __init__(self) -> None:
        super().__init__("sorting_arm_control_node")

        # 参数化：避免把话题名/设备 id 写死，便于多设备/多场景复用与 launch 重映射
        self.declare_parameter("cmd_topic", "/sorting_arm/cmd")
        self.declare_parameter("status_topic", "/sorting_arm/status")
        self.declare_parameter("device_id", "arm_01")
        self.declare_parameter("default_scene", "sorting")
        self.declare_parameter("queue_maxsize", 50)
        self.declare_parameter("dedup_maxsize", 2000)

        self._cmd_topic = str(self.get_parameter("cmd_topic").value)
        self._status_topic = str(self.get_parameter("status_topic").value)
        self._device_id = str(self.get_parameter("device_id").value)
        self._default_scene = str(self.get_parameter("default_scene").value)
        self._queue_maxsize = int(self.get_parameter("queue_maxsize").value)
        self._dedup_maxsize = int(self.get_parameter("dedup_maxsize").value)

        self._driver = MockSortingArmDriver()
        self._enabled = True
        self._guard_closed = True

        # 状态机：课堂最小集（idle/running/error/estop）
        self._state = "idle"

        # 去重集合：用于处理工具端重试/断线重连导致的重复下发；用队列限制最大尺寸，避免无限增长
        self._handled_cmd_ids: set[str] = set()
        self._handled_cmd_id_order: deque[str] = deque()

        # 指令队列：把“解析/回执”和“驱动执行”解耦，避免 ROS2 回调被执行耗时阻塞
        self._cmd_queue: queue.Queue[DeviceCommand] = queue.Queue(maxsize=self._queue_maxsize)

        self._cmd_sub = self.create_subscription(String, self._cmd_topic, self._on_cmd, 10)
        self._status_pub = self.create_publisher(String, self._status_topic, 10)

        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

        self.get_logger().info(
            json.dumps(
                {
                    "event": "node_started",
                    "node": self.get_name(),
                    "cmd_topic": self._cmd_topic,
                    "status_topic": self._status_topic,
                    "device_id": self._device_id,
                },
                ensure_ascii=False,
            )
        )

    def _remember_cmd_id(self, cmd_id: str) -> None:
        # 简易 LRU：只记录最近 N 条 cmd_id，实现端侧幂等（同 cmd_id 不重复执行）
        self._handled_cmd_ids.add(cmd_id)
        self._handled_cmd_id_order.append(cmd_id)
        while len(self._handled_cmd_id_order) > self._dedup_maxsize:
            old = self._handled_cmd_id_order.popleft()
            self._handled_cmd_ids.discard(old)

    def _publish_status(
        self,
        last_cmd_id: str,
        ok: bool,
        code: str,
        message: str,
        state: str | None = None,
        detail: dict[str, Any] | None = None,
        trace_id: str | None = None,
        msg_id: str | None = None,
        event: str | None = None,
    ) -> None:
        # 课堂统一回执口径：last_cmd_id/ok/code/message 必备；可选带回 trace_id/msg_id/event 做跨端追踪
        payload: dict[str, Any] = {
            "device_type": "arm",
            "device_id": self._device_id,
            "state": state or self._state,
            "last_cmd_id": last_cmd_id,
            "ok": ok,
            "code": code,
            "message": message,
            "detail": detail or {},
            "ts_ms": now_ms(),
        }
        if trace_id is not None:
            payload["trace_id"] = trace_id
        if msg_id is not None:
            payload["msg_id"] = msg_id
        if event is not None:
            payload["event"] = event

        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self._status_pub.publish(msg)

    def _on_cmd(self, msg: String) -> None:
        # 订阅回调：只做“解析+快速回执+入队”，不做耗时执行
        parse_ok, result = self._parse_and_validate(msg.data)
        if not parse_ok:
            last_cmd_id = result.get("cmd_id") or "UNKNOWN"
            self._publish_status(
                last_cmd_id,
                False,
                result["code"],
                result["message"],
                state="error",
                trace_id=result.get("trace_id"),
                msg_id=result.get("msg_id"),
                event=result.get("event"),
            )
            return

        cmd: DeviceCommand = result["cmd"]

        # 幂等：同 cmd_id 重复到达时，不重复执行，直接回执 DUPLICATE
        if cmd.cmd_id in self._handled_cmd_ids:
            self._publish_status(
                cmd.cmd_id,
                True,
                "DUPLICATE",
                "cmd_id already handled; ignored",
                trace_id=cmd.trace_id,
                msg_id=cmd.msg_id,
                event=cmd.event,
            )
            return

        # 急停最高优先级：立即生效 + 清空队列，避免后续指令继续执行
        if cmd.action in {"e_stop", "estop"}:
            self._remember_cmd_id(cmd.cmd_id)
            self._state = "estop"
            self._driver.e_stop()
            self._drain_queue()
            self._publish_status(
                cmd.cmd_id,
                True,
                "ESTOP",
                "emergency stop triggered",
                state="estop",
                trace_id=cmd.trace_id,
                msg_id=cmd.msg_id,
                event=cmd.event,
            )
            return

        if not self._check_safety(cmd):
            self._remember_cmd_id(cmd.cmd_id)
            self._state = "error"
            self._publish_status(
                cmd.cmd_id,
                False,
                "SAFETY_BLOCK",
                "safety precondition not satisfied",
                state="error",
                trace_id=cmd.trace_id,
                msg_id=cmd.msg_id,
                event=cmd.event,
            )
            return

        try:
            self._cmd_queue.put_nowait(cmd)
        except queue.Full:
            self._publish_status(
                cmd.cmd_id,
                False,
                "QUEUE_FULL",
                "device busy; command queue is full",
                state="error",
                trace_id=cmd.trace_id,
                msg_id=cmd.msg_id,
                event=cmd.event,
            )
            return

        self._remember_cmd_id(cmd.cmd_id)
        self._state = "running"
        self._publish_status(
            cmd.cmd_id,
            True,
            "ACCEPTED",
            "command accepted",
            state="running",
            trace_id=cmd.trace_id,
            msg_id=cmd.msg_id,
            event=cmd.event,
        )

    def _drain_queue(self) -> None:
        while True:
            try:
                _ = self._cmd_queue.get_nowait()
            except queue.Empty:
                break

    def _check_safety(self, cmd: DeviceCommand) -> bool:
        # 最小安全门禁：课堂只演示两个前置条件；工程落地可扩展为更多联锁与权限
        safety = cmd.safety or {}
        require_enable = bool(safety.get("require_enable", False))
        require_guard_closed = bool(safety.get("require_guard_closed", False))
        if require_enable and not self._enabled:
            return False
        if require_guard_closed and not self._guard_closed:
            return False
        return True

    def _worker_loop(self) -> None:
        # 后台执行线程：串行执行驱动调用，避免并发导致的设备状态竞态
        while rclpy.ok():
            try:
                cmd = self._cmd_queue.get(timeout=0.2)
            except queue.Empty:
                if self._state == "running":
                    self._state = "idle"
                continue

            try:
                self._execute(cmd)
            except Exception as e:
                self._state = "error"
                self._publish_status(
                    cmd.cmd_id,
                    False,
                    "EXEC_ERROR",
                    str(e),
                    state="error",
                    trace_id=cmd.trace_id,
                    msg_id=cmd.msg_id,
                    event=cmd.event,
                )
            else:
                self._state = "idle"
                self._publish_status(
                    cmd.cmd_id,
                    True,
                    "OK",
                    f"{cmd.action} finished",
                    state="idle",
                    trace_id=cmd.trace_id,
                    msg_id=cmd.msg_id,
                    event=cmd.event,
                )

    def _execute(self, cmd: DeviceCommand) -> None:
        # 动作路由：把 action 映射到驱动层 API；这里就是“结构化指令 -> 可执行动作”的关键落点
        if cmd.action == "home":
            self._driver.home()
            return

        if cmd.action == "pick_place":
            from_bin = str(cmd.params.get("from", "")).strip()
            to_bin = str(cmd.params.get("to", "")).strip()
            speed = float(cmd.params.get("speed", 0.5))
            if not from_bin or not to_bin:
                raise ValueError("pick_place requires params.from and params.to")
            self._driver.pick_place(from_bin, to_bin, speed)
            return

        if cmd.action == "stop":
            self._driver.stop()
            return

        raise ValueError(f"unknown action: {cmd.action}")

    def _parse_and_validate(self, raw: str) -> tuple[bool, dict[str, Any]]:
        # 解析与校验（端侧二次校验）：永远不信任上游
        try:
            obj = json.loads(raw)
        except Exception:
            return False, {"cmd_id": "UNKNOWN", "code": "BAD_JSON", "message": "cmd must be a JSON string"}

        trace_id = None
        msg_id = None
        event = None
        topic = None

        data: dict[str, Any] | None
        if isinstance(obj, dict) and "schema_version" in obj and "payload" in obj:
            # 兼容 23 讲义的 Envelope：payload 承载业务体（这里期望 payload 是 ArmCommand）
            trace_id = str(obj.get("trace_id")) if obj.get("trace_id") is not None else None
            msg_id = str(obj.get("msg_id")) if obj.get("msg_id") is not None else None
            event = str(obj.get("event")) if obj.get("event") is not None else None
            topic = str(obj.get("topic")) if obj.get("topic") is not None else None

            payload = obj.get("payload")
            if not isinstance(payload, dict):
                return False, {
                    "cmd_id": msg_id or "UNKNOWN",
                    "trace_id": trace_id,
                    "msg_id": msg_id,
                    "event": event,
                    "code": "BAD_ENVELOPE",
                    "message": "envelope.payload must be an object",
                }
            data = payload
        elif isinstance(obj, dict):
            data = obj
        else:
            return False, {"cmd_id": "UNKNOWN", "code": "BAD_BODY", "message": "cmd must be a JSON object or Envelope"}

        def infer_device_type(in_topic: str | None, in_event: str | None) -> str | None:
            # 兼容策略：课堂允许从 event/topic 推断设备类型，工程落地建议显式提供 device_type
            if in_event and in_event.startswith("arm."):
                return "arm"
            if in_topic and "/sorting_arm/" in in_topic:
                return "arm"
            return None

        cmd_id = data.get("cmd_id") or msg_id
        cmd_id_str = str(cmd_id).strip() if cmd_id is not None else ""
        if not cmd_id_str:
            return False, {
                "cmd_id": "UNKNOWN",
                "trace_id": trace_id,
                "msg_id": msg_id,
                "event": event,
                "code": "MISSING_FIELD",
                "message": "missing field: cmd_id (or envelope.msg_id)",
            }

        scene = str(data.get("scene") or self._default_scene).strip()
        device_type = data.get("device_type") or infer_device_type(topic, event)
        device_type_str = str(device_type).strip() if device_type is not None else ""
        device_id = data.get("device_id")
        device_id_str = str(device_id).strip() if device_id is not None else ""
        action = data.get("action")
        action_str = str(action).strip() if action is not None else ""
        params = data.get("params")
        ts_ms = data.get("ts_ms") if data.get("ts_ms") is not None else obj.get("ts_ms") if isinstance(obj, dict) else None

        missing: list[str] = []
        if not device_id_str:
            missing.append("device_id")
        if not device_type_str:
            missing.append("device_type")
        if not action_str:
            missing.append("action")
        if params is None:
            missing.append("params")
        if ts_ms is None:
            missing.append("ts_ms")
        if missing:
            return False, {
                "cmd_id": cmd_id_str,
                "trace_id": trace_id,
                "msg_id": msg_id,
                "event": event,
                "code": "MISSING_FIELD",
                "message": f"missing fields: {missing}",
            }

        if not isinstance(params, dict):
            return False, {
                "cmd_id": cmd_id_str,
                "trace_id": trace_id,
                "msg_id": msg_id,
                "event": event,
                "code": "BAD_PARAMS",
                "message": "params must be an object",
            }

        try:
            ts_ms_int = int(ts_ms)
        except Exception:
            return False, {
                "cmd_id": cmd_id_str,
                "trace_id": trace_id,
                "msg_id": msg_id,
                "event": event,
                "code": "BAD_FIELD_TYPE",
                "message": "ts_ms must be integer milliseconds",
            }

        cmd = DeviceCommand(
            cmd_id=cmd_id_str,
            scene=scene,
            device_type=device_type_str,
            device_id=device_id_str,
            action=action_str,
            params=dict(params),
            safety=dict(data.get("safety") or {}),
            meta=dict(data.get("meta") or {}),
            ts_ms=ts_ms_int,
            trace_id=trace_id,
            msg_id=msg_id,
            event=event,
            topic=topic,
        )
        return True, {"cmd": cmd}


def main() -> None:
    rclpy.init()
    node = SortingArmControlNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
