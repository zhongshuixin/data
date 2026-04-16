"""
标注指令数据解析与“规则识别器”评估脚本（仅依赖 Python 标准库）。

用途（对应 16 讲义第二课时）：
- 读取 JSONL/CSV 标注数据
- 输出：动作分布、同义表达建议、基于规则的识别器评估（top-1 准确率）

注意：
- 本脚本目标是“课堂最小可复现 + 可解释 + 可回归”，不是追求 SOTA 模型效果。
"""

import argparse
import csv
import difflib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FILLER_WORDS = ["帮我", "麻烦", "请", "一下", "立刻", "马上", "给我"]


def normalize_text(text: str) -> str:
    # 规范化输入：去口头语/空格/标点，让“同一句话的不同写法”更容易匹配到同一规则
    t = text.strip().lower()
    for w in FILLER_WORDS:
        t = t.replace(w, "")
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[，。！？,.!?;；:：]", "", t)
    return t


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    # JSONL：每行一个 JSON 对象，适合版本管理与追加
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def load_csv(path: Path) -> list[dict[str, Any]]:
    # CSV：方便用表格编辑，但 slots 需要以 JSON 字符串保存（列名建议 slots_json）
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
    # 一条规则：用正则或其他方式把输入映射到 canonical_action
    canonical_action: str
    mode: str
    pattern: str


def build_synonym_suggestions(samples: list[dict[str, Any]], limit_per_action: int) -> dict[str, list[str]]:
    # 从标注样本聚合“常见说法”（高频表达），用于补齐精确匹配与正则规则
    action_phrases: dict[str, Counter[str]] = defaultdict(Counter)
    for s in samples:
        raw = str(s["raw_text"]).strip()
        canonical = str(s["canonical_action"])
        if raw:
            action_phrases[canonical][raw] += 1
    return {k: [p for p, _ in c.most_common(limit_per_action)] for k, c in action_phrases.items()}


def build_rules(samples: list[dict[str, Any]]) -> tuple[dict[str, str], list[Rule]]:
    # 规则生成策略（三段式中的前两段）：
    # 1) exact_map：标注样本直接生成“规范化文本 -> canonical_action”的精确匹配表
    # 2) regex_rules：补充少量强规则（尤其是安全动作：急停/停止）
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
            Rule("arm.e_stop", "regex", r"(急停|紧急停止|estop|e-stop|stopnow)"),
            Rule("arm.stop", "regex", r"(停下|停止|别动|暂停)"),
            Rule("arm.home", "regex", r"(回零|回原点|归零|home)"),
        ]
    )
    return exact_map, regex_rules


def recognize_action(
    text: str,
    exact_map: dict[str, str],
    regex_rules: list[Rule],
    fuzzy_threshold: float,
) -> tuple[str | None, str]:
    # 三段式识别：exact -> regex -> fuzzy（兜底）
    norm = normalize_text(text)
    if norm in exact_map:
        return exact_map[norm], "exact"

    for rule in regex_rules:
        if re.search(rule.pattern, norm):
            return rule.canonical_action, "regex"

    # fuzzy：只作为兜底，阈值需要用标注数据调参；工业控制宁可拒绝也不要误判
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


def evaluate(
    samples: list[dict[str, Any]],
    exact_map: dict[str, str],
    regex_rules: list[Rule],
    fuzzy_threshold: float,
) -> dict[str, Any]:
    # 用标注数据评估识别器：输出 top-1 准确率与前 10 条错误样本，便于下一轮优化
    total = len(samples)
    hit = 0
    mode_counter: Counter[str] = Counter()
    errors: list[dict[str, Any]] = []

    for s in samples:
        raw = str(s["raw_text"])
        gt = str(s["canonical_action"])
        pred, mode = recognize_action(raw, exact_map, regex_rules, fuzzy_threshold)
        mode_counter[mode] += 1
        if pred == gt:
            hit += 1
        else:
            errors.append({"raw_text": raw, "gt": gt, "pred": pred, "mode": mode})

    return {
        "total": total,
        "hit": hit,
        "acc": (hit / total) if total else 0.0,
        "mode_counter": dict(mode_counter),
        "errors_top10": errors[:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--format", choices=["jsonl", "csv"], default=None)
    parser.add_argument("--fuzzy-threshold", type=float, default=0.82)
    parser.add_argument("--synonym-topk", type=int, default=5)
    args = parser.parse_args()

    # 自动推断输入格式：--format 不填时，按文件后缀决定
    if args.format is None:
        fmt = args.input.suffix.lower().lstrip(".")
    else:
        fmt = args.format

    if fmt == "jsonl":
        samples = load_jsonl(args.input)
    elif fmt == "csv":
        samples = load_csv(args.input)
    else:
        raise SystemExit("format must be jsonl or csv")

    action_dist = Counter(str(s["canonical_action"]) for s in samples)
    synonym_suggestions = build_synonym_suggestions(samples, args.synonym_topk)
    exact_map, regex_rules = build_rules(samples)
    report = evaluate(samples, exact_map, regex_rules, args.fuzzy_threshold)

    out = {
        "action_dist": dict(action_dist),
        "synonym_suggestions": synonym_suggestions,
        "fuzzy_threshold": args.fuzzy_threshold,
        "report": report,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
