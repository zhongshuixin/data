"""
把“人话/语音转写”识别为结构化 ArmCommand，并通过 rosbridge 下发到 ROS2 端。

用途（对应 16 讲义第二课时项目工坊）：
- 用标注数据生成规则（exact/regex/fuzzy）
- 把输入文本识别成 canonical_action
- 生成 ArmCommand（cmd_id/action/params/ts_ms）
- rosbridge publish 到 /sorting_arm/cmd（std_msgs/String，data 内是 JSON 字符串）

安全口径（课堂统一）：
- 不确定就拒绝（不给设备“猜测控制”）
- 急停/停止优先级高
- pick_place 需要 slots 参数（from/to/speed），缺参直接拒绝
"""

import argparse
import csv
import difflib
import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FILLER_WORDS = ["帮我", "麻烦", "请", "一下", "立刻", "马上", "给我"]


def now_ms() -> int:
    return int(time.time() * 1000)


def normalize_text(text: str) -> str:
    t = text.strip().lower()
    for w in FILLER_WORDS:
        t = t.replace(w, "")
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[，。！？,.!?;；:：]", "", t)
    return t


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def load_csv(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slots = json.loads(row.get("slots_json") or "{}")
            items.append(
                {
                    "raw_text": row["raw_text"],
                    "canonical_action": row["canonical_action"],
                    "slots": slots,
                }
            )
    return items


@dataclass(frozen=True)
class Rule:
    canonical_action: str
    pattern: str


def build_rules(samples: list[dict[str, Any]]) -> tuple[dict[str, str], list[Rule]]:
    exact_map: dict[str, str] = {}
    regex_rules: list[Rule] = []

    for s in samples:
        raw = str(s["raw_text"])
        canonical = str(s["canonical_action"])
        norm = normalize_text(raw)
        if norm and norm not in exact_map:
            exact_map[norm] = canonical

    regex_rules.extend(
        [
            Rule("arm.e_stop", r"(急停|紧急停止|estop|e-stop|stopnow)"),
            Rule("arm.stop", r"(停下|停止|别动|暂停)"),
            Rule("arm.home", r"(回零|回原点|归零|home)"),
        ]
    )
    return exact_map, regex_rules


def recognize_action(
    text: str,
    exact_map: dict[str, str],
    regex_rules: list[Rule],
    fuzzy_threshold: float,
) -> tuple[str | None, str]:
    norm = normalize_text(text)
    if norm in exact_map:
        return exact_map[norm], "exact"

    for rule in regex_rules:
        if re.search(rule.pattern, norm):
            return rule.canonical_action, "regex"

    best_action = None
    best_score = 0.0
    for k, action in exact_map.items():
        score = difflib.SequenceMatcher(a=norm, b=k).ratio()
        if score > best_score:
            best_action = action
            best_score = score

    if best_action is not None and best_score >= fuzzy_threshold:
        return best_action, f"fuzzy:{best_score:.2f}"

    return None, "reject"


def rosbridge_publish(ws, topic: str, msg: dict[str, Any]) -> None:
    payload = {"op": "publish", "topic": topic, "msg": msg}
    ws.send(json.dumps(payload, ensure_ascii=False))


def canonical_to_action(canonical_action: str) -> str | None:
    if canonical_action == "arm.home":
        return "home"
    if canonical_action == "arm.stop":
        return "stop"
    if canonical_action == "arm.e_stop":
        return "e_stop"
    if canonical_action == "arm.pick_place":
        return "pick_place"
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ws-url", default=os.environ.get("ROSBRIDGE_WS_URL", "ws://localhost:9090"))
    parser.add_argument("--topic", default="/sorting_arm/cmd")
    parser.add_argument("--device-id", default="arm_01")
    parser.add_argument("--scene", default="sorting")
    parser.add_argument("--user", default="stu01")
    parser.add_argument("--role", default="operator")
    parser.add_argument("--cmd-id", default=f"C-{time.strftime('%Y%m%d')}-{int(time.time() * 1000)}")

    parser.add_argument("--data", type=Path, default=Path("data/command_annotations_example.jsonl"))
    parser.add_argument("--format", choices=["jsonl", "csv"], default="jsonl")
    parser.add_argument("--fuzzy-threshold", type=float, default=0.82)

    parser.add_argument("--text", required=True)
    parser.add_argument("--slots-json", default=None)
    args = parser.parse_args()

    try:
        from websocket import create_connection
    except Exception:
        raise SystemExit("missing dependency: websocket-client (pip install -r requirements.txt)")

    if args.format == "jsonl":
        samples = load_jsonl(args.data)
    else:
        samples = load_csv(args.data)

    exact_map, regex_rules = build_rules(samples)
    canonical, mode = recognize_action(args.text, exact_map, regex_rules, args.fuzzy_threshold)
    if canonical is None:
        print(json.dumps({"ok": False, "code": "REJECT", "message": "cannot recognize command", "mode": mode}, ensure_ascii=False))
        raise SystemExit(2)

    action = canonical_to_action(canonical)
    if action is None:
        print(json.dumps({"ok": False, "code": "UNSUPPORTED", "message": f"unsupported canonical_action: {canonical}"}, ensure_ascii=False))
        raise SystemExit(3)

    slots = json.loads(args.slots_json) if args.slots_json else {}
    if not isinstance(slots, dict):
        raise SystemExit("--slots-json must be a JSON object")

    if action == "pick_place":
        from_bin = str(slots.get("from", "")).strip()
        to_bin = str(slots.get("to", "")).strip()
        if not from_bin or not to_bin:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "code": "MISSING_SLOTS",
                        "message": "pick_place requires slots_json with from/to (and optional speed)",
                        "canonical_action": canonical,
                        "mode": mode,
                    },
                    ensure_ascii=False,
                )
            )
            raise SystemExit(4)

    cmd = {
        "cmd_id": args.cmd_id,
        "scene": args.scene,
        "device_type": "arm",
        "device_id": args.device_id,
        "action": action,
        "params": slots,
        "safety": {"require_enable": True, "require_guard_closed": True},
        "meta": {"user": args.user, "role": args.role, "source": "tool"},
        "ts_ms": now_ms(),
    }

    cmd_json = json.dumps(cmd, ensure_ascii=False)
    msg = {"data": cmd_json}

    ws = create_connection(args.ws_url, timeout=5)
    try:
        rosbridge_publish(ws, args.topic, msg)
        print(
            json.dumps(
                {
                    "ok": True,
                    "cmd_id": args.cmd_id,
                    "canonical_action": canonical,
                    "action": action,
                    "mode": mode,
                    "ws_url": args.ws_url,
                    "topic": args.topic,
                },
                ensure_ascii=False,
            )
        )
    finally:
        ws.close()


if __name__ == "__main__":
    main()
