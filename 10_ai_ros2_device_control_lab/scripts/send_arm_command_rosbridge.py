"""
通过 rosbridge 下发结构化机械臂控制指令（ArmCommand）的最小脚本。

用途（对应 16 讲义第一/二课时衔接）：
- 工具端生成结构化 ArmCommand（含 cmd_id/ts_ms/safety）
- 通过 rosbridge 的 publish 协议，发布到 /sorting_arm/cmd（std_msgs/String，data 内是 JSON 字符串）
"""

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any


def now_ms() -> int:
    # 统一使用毫秒时间戳，便于排查延迟/重放/乱序
    return int(time.time() * 1000)


@dataclass(frozen=True)
class ArmCommand:
    # 课堂统一的最小控制指令骨架（应用层协议），最终会被 ROS2 端解析与执行
    cmd_id: str
    scene: str
    device_type: str
    device_id: str
    action: str
    params: dict[str, Any]
    safety: dict[str, Any]
    meta: dict[str, Any]
    ts_ms: int


def build_arm_command(
    cmd_id: str,
    action: str,
    device_id: str,
    scene: str,
    user: str,
    role: str,
    params_json: str | None,
) -> ArmCommand:
    # params 以 JSON 字符串输入，便于命令行快速构造；必须是 object，避免传入数组/字符串导致端侧解析困难
    params = json.loads(params_json) if params_json else {}
    if not isinstance(params, dict):
        raise SystemExit("--params must be a JSON object")
    return ArmCommand(
        cmd_id=cmd_id,
        scene=scene,
        device_type="arm",
        device_id=device_id,
        action=action,
        params=params,
        # safety 是端侧安全门禁的输入，课堂阶段用固定字段，后续可扩展为更细的联锁条件
        safety={"require_enable": True, "require_guard_closed": True},
        meta={"user": user, "role": role, "source": "tool"},
        ts_ms=now_ms(),
    )


def rosbridge_publish(ws, topic: str, msg: dict[str, Any]) -> None:
    # rosbridge publish 结构：op/topic/msg，其中 msg 需符合目标 ROS2 消息类型结构
    # 这里目标类型为 std_msgs/String，因此 msg 必须是 {"data": "<JSON字符串>"}
    payload = {"op": "publish", "topic": topic, "msg": msg}
    ws.send(json.dumps(payload, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ws-url", default=os.environ.get("ROSBRIDGE_WS_URL", "ws://localhost:9090"))
    parser.add_argument("--topic", default="/sorting_arm/cmd")
    parser.add_argument("--device-id", default="arm_01")
    parser.add_argument("--scene", default="sorting")
    parser.add_argument("--cmd-id", default=f"C-{time.strftime('%Y%m%d')}-{int(time.time() * 1000)}")
    parser.add_argument("--action", required=True, choices=["home", "pick_place", "stop", "e_stop"])
    parser.add_argument("--params", default=None)
    parser.add_argument("--user", default="stu01")
    parser.add_argument("--role", default="operator")
    args = parser.parse_args()

    # websocket-client 是工具端依赖；ROS2 端不需要该库
    try:
        from websocket import create_connection
    except Exception:
        raise SystemExit("missing dependency: websocket-client (pip install -r requirements.txt)")

    cmd = build_arm_command(
        cmd_id=args.cmd_id,
        action=args.action,
        device_id=args.device_id,
        scene=args.scene,
        user=args.user,
        role=args.role,
        params_json=args.params,
    )

    # 注意：这里把 ArmCommand 序列化为字符串，再放入 std_msgs/String.data
    cmd_json = json.dumps(cmd.__dict__, ensure_ascii=False)
    msg = {"data": cmd_json}

    # 只做“下发一次并退出”，把可靠性策略（重试/超时/等待回执）留给更上层的 Tool/Web 封装
    ws = create_connection(args.ws_url, timeout=5)
    try:
        rosbridge_publish(ws, args.topic, msg)
        print(json.dumps({"ok": True, "ws_url": args.ws_url, "topic": args.topic, "cmd_id": cmd.cmd_id}, ensure_ascii=False))
    finally:
        ws.close()


if __name__ == "__main__":
    main()
