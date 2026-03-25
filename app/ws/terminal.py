"""터미널 WebSocket 핸들러."""
import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

from app.auth import verify_session_cookie, COOKIE_NAME
from app.services.terminal_service import terminal_manager


async def terminal_websocket(websocket: WebSocket, session_id: str) -> None:
    """터미널 세션 WebSocket 양방향 연결."""
    # 쿠키 인증
    cookie = websocket.cookies.get(COOKIE_NAME)
    if not cookie or not verify_session_cookie(cookie):
        await websocket.close(code=4001, reason="Not authenticated")
        return

    session = terminal_manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()

    async def ws_to_process() -> None:
        """WebSocket → 프로세스 stdin."""
        try:
            while True:
                data = await websocket.receive_text()
                # JSON 제어 메시지 분기
                if data.startswith("{"):
                    try:
                        msg = json.loads(data)
                        msg_type = msg.get("type")
                        if msg_type == "resize":
                            session.resize(msg.get("cols", 120), msg.get("rows", 30))
                            continue
                        if msg_type == "ping":
                            await websocket.send_text('{"type":"pong"}')
                            continue
                    except (json.JSONDecodeError, ValueError):
                        pass
                # 일반 키 입력 → 프로세스에 전달 + 에코 (PIPE 모드용)
                raw = data.encode("utf-8")
                await session.write(raw)
                # PIPE 모드에서는 에코가 안 되므로 수동 에코
                if session._master_fd is None and session._winpty is None:
                    await websocket.send_text(data)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    async def process_to_ws() -> None:
        """프로세스 stdout → WebSocket (큐 기반)."""
        try:
            while session.is_alive:
                output = await session.read()
                if output == b"":
                    # 빈 바이트 = 타임아웃 또는 종료 시그널
                    if not session.is_alive:
                        break
                    continue
                text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
                await websocket.send_text(text)
        except Exception:
            pass
        try:
            await websocket.send_text(json.dumps({"type": "exit", "code": 0}))
        except Exception:
            pass

    try:
        await asyncio.gather(ws_to_process(), process_to_ws())
    except Exception:
        pass
    finally:
        # 세션은 유지 (탭 전환 후 재연결 가능), 명시적 삭제만 kill
        pass
