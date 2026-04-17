import json
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


def now_ms() -> int:
    # 统一毫秒时间戳：用于消息 ts / 默认 id，便于前后端对齐“先后顺序”
    return int(time.time() * 1000)


def make_msg(msg_type: str, payload: Any, msg_id: str | None = None) -> dict[str, Any]:
    # 统一消息 Envelope：type / id / ts / payload
    # 前端 useReconnectingWebSocket 里的 sendEnvelope 也按这个结构发送，便于双向对齐与扩展
    return {"type": msg_type, "id": msg_id or str(now_ms()), "ts": now_ms(), "payload": payload}


def try_parse_json(text: str) -> dict[str, Any] | None:
    # 降级解析：不是 JSON 或不是对象结构就返回 None
    # 目的：避免因为某条消息解析失败导致整个连接循环异常退出
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    # WebSocket 必须先 accept 才能开始收发；否则浏览器通常表现为“秒断/握手失败”
    await ws.accept()
    # 连接建立后先发一条 system，用作“连接已成功”的可观察证据
    await ws.send_text(json.dumps(make_msg("system", {"info": "connected"}), ensure_ascii=False))

    try:
        while True:
            # 等待客户端发来文本帧（前端发送的是 JSON 字符串）
            text = await ws.receive_text()
            data = try_parse_json(text)
            if not data:
                # 客户端发来的不是 JSON：直接回显，确保最小可用（便于课堂联调）
                await ws.send_text(text)
                continue

            t = data.get("type")
            if t == "ping":
                # 心跳：收到 ping 必须尽快回 pong
                # 前端依赖 pong/任意消息更新 lastMessageAt，用于断线检测与重连触发
                await ws.send_text(json.dumps(make_msg("pong", {}), ensure_ascii=False))
                continue

            if t == "chat":
                # 课堂演示：chat 做 echo
                # 断线恢复后仍能收发，是验收重连机制是否可用的关键测试点
                payload = data.get("payload")
                await ws.send_text(json.dumps(make_msg("chat", {"echo": payload}), ensure_ascii=False))
                continue

            # 未识别的 type：返回 system，避免客户端“发了但没回包”导致误判
            await ws.send_text(json.dumps(make_msg("system", {"ok": True}), ensure_ascii=False))
    except WebSocketDisconnect:
        # 客户端断开属于正常控制流：不当作错误处理
        return
