"""웹 터미널 세션 관리 — 크로스 플랫폼 PTY."""
import asyncio
import os
import platform
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import get_settings

SYSTEM = platform.system()
MAX_SESSIONS = 10
IDLE_TIMEOUT = 1800  # 30분

# 크로스 플랫폼 PTY import
if SYSTEM != "Windows":
    import pty as pty_mod  # type: ignore[import-untyped]
    import fcntl
    import struct
    import termios
    import signal

try:
    from winpty import PtyProcess as WinPtyProcess  # type: ignore[import-untyped]
    HAS_WINPTY = True
except ImportError:
    HAS_WINPTY = False


@dataclass
class TerminalSession:
    session_id: str
    project_id: int | None
    project_slug: str
    shell: str
    cwd: str
    cols: int = 120
    rows: int = 30
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "running"
    # 플랫폼별 핸들
    _process: asyncio.subprocess.Process | None = field(default=None, repr=False)
    _master_fd: int | None = field(default=None, repr=False)
    _winpty: object | None = field(default=None, repr=False)
    # 출력 큐 (스레드 → asyncio 전달)
    _output_queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(), repr=False)
    _reader_thread: threading.Thread | None = field(default=None, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def touch(self) -> None:
        self.last_activity = datetime.now(timezone.utc)

    def is_idle(self) -> bool:
        return (datetime.now(timezone.utc) - self.last_activity).total_seconds() > IDLE_TIMEOUT

    def _start_reader_thread(self) -> None:
        """별도 스레드에서 PTY/PIPE 출력을 읽어서 큐에 넣기."""
        if self._winpty is not None:
            def _winpty_read_loop() -> None:
                while not self._stop_event.is_set():
                    try:
                        data = self._winpty.read(4096)  # type: ignore[union-attr]
                        if data:
                            self._output_queue.put_nowait(data.encode("utf-8"))
                        else:
                            break
                    except EOFError:
                        break
                    except Exception:
                        break
                self._output_queue.put_nowait(b"")

            self._reader_thread = threading.Thread(target=_winpty_read_loop, daemon=True)
            self._reader_thread.start()
            return

        if self._process and self._process.stdout:
            # subprocess PIPE — asyncio 기반 reader를 별도 task로
            asyncio.get_event_loop().create_task(self._async_pipe_reader())
            return

        def _read_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    if self._master_fd is not None:
                        data = os.read(self._master_fd, 4096)
                        if data:
                            self._output_queue.put_nowait(data)
                        else:
                            break
                    else:
                        break
                except (OSError, EOFError):
                    break
                except Exception:
                    break
            self._output_queue.put_nowait(b"")

        self._reader_thread = threading.Thread(target=_read_loop, daemon=True)
        self._reader_thread.start()

    async def _async_pipe_reader(self) -> None:
        """subprocess PIPE stdout을 asyncio로 읽어서 큐에 넣기."""
        try:
            while self._process and self._process.stdout:
                data = await self._process.stdout.read(4096)
                if data:
                    self._output_queue.put_nowait(data)
                else:
                    break
        except Exception:
            pass
        self._output_queue.put_nowait(b"")

    async def write(self, data: bytes) -> None:
        self.touch()
        if self._winpty is not None:
            self._winpty.write(data.decode("utf-8", errors="replace"))  # type: ignore[union-attr]
        elif self._master_fd is not None:
            os.write(self._master_fd, data)
        elif self._process and self._process.stdin:
            self._process.stdin.write(data)
            await self._process.stdin.drain()

    async def read(self) -> bytes:
        """큐에서 출력 데이터 가져오기 (비동기, non-blocking)."""
        self.touch()
        try:
            return await asyncio.wait_for(self._output_queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            return b""

    def resize(self, cols: int, rows: int) -> None:
        self.cols = cols
        self.rows = rows
        if SYSTEM != "Windows" and self._master_fd is not None:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
        elif self._winpty is not None:
            try:
                self._winpty.setwinsize(rows, cols)  # type: ignore[union-attr]
            except Exception:
                pass

    async def kill(self) -> None:
        self.status = "exited"
        self._stop_event.set()
        if SYSTEM != "Windows" and self._process and self._process.pid:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        if self._process:
            try:
                self._process.kill()
            except (ProcessLookupError, OSError):
                pass
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None
        if self._winpty is not None:
            try:
                self._winpty.close()  # type: ignore[union-attr]
            except Exception:
                pass
            self._winpty = None

    @property
    def is_alive(self) -> bool:
        if self._winpty is not None:
            try:
                return self._winpty.isalive()  # type: ignore[union-attr]
            except Exception:
                return False
        if self._process:
            return self._process.returncode is None
        return False


class TerminalSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, TerminalSession] = {}

    async def create_session(
        self, project_id: int | None = None, project_slug: str = "",
        shell: str = "auto", cwd: str = "", cols: int = 120, rows: int = 30,
    ) -> TerminalSession:
        if len(self._sessions) >= MAX_SESSIONS:
            await self._cleanup_idle()
            if len(self._sessions) >= MAX_SESSIONS:
                raise RuntimeError(f"최대 세션 수({MAX_SESSIONS}) 초과")

        session_id = uuid.uuid4().hex[:8]
        resolved_cwd = self._resolve_cwd(project_slug, cwd)
        resolved_shell = self._resolve_shell(shell)

        session = TerminalSession(
            session_id=session_id,
            project_id=project_id,
            project_slug=project_slug,
            shell=resolved_shell,
            cwd=resolved_cwd,
            cols=cols,
            rows=rows,
        )

        await self._spawn(session)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> TerminalSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        return [
            {
                "session_id": s.session_id,
                "project_id": s.project_id,
                "project_slug": s.project_slug,
                "shell": s.shell,
                "cwd": s.cwd,
                "status": "running" if s.is_alive else "exited",
                "created_at": s.created_at.isoformat(),
            }
            for s in self._sessions.values()
        ]

    async def kill_session(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session:
            await session.kill()
            return True
        return False

    async def cleanup_all(self) -> None:
        for sid in list(self._sessions.keys()):
            await self.kill_session(sid)

    async def _cleanup_idle(self) -> None:
        idle = [sid for sid, s in self._sessions.items() if s.is_idle() or not s.is_alive]
        for sid in idle:
            await self.kill_session(sid)

    def _resolve_cwd(self, project_slug: str, cwd: str) -> str:
        if cwd and os.path.isdir(cwd):
            return cwd
        settings = get_settings()
        base = settings.terminal_projects_dir
        if base and project_slug:
            project_dir = os.path.join(base, project_slug)
            if os.path.isdir(project_dir):
                return project_dir
        if base and os.path.isdir(base):
            return base
        return os.path.expanduser("~")

    def _resolve_shell(self, shell: str) -> str:
        if shell != "auto":
            return shell
        if SYSTEM == "Windows":
            return "cmd"
        return "bash"

    async def _spawn(self, session: TerminalSession) -> None:
        if SYSTEM == "Windows":
            await self._spawn_windows(session)
        else:
            await self._spawn_unix(session)
        # 출력 읽기 스레드 시작
        session._start_reader_thread()

    async def _spawn_unix(self, session: TerminalSession) -> None:
        cmd_map = {
            "bash": ["/bin/bash", "--login"],
            "zsh": ["/bin/zsh", "--login"],
            "sh": ["/bin/sh"],
        }
        cmd = cmd_map.get(session.shell, ["/bin/bash", "--login"])

        master_fd, slave_fd = pty_mod.openpty()
        winsize = struct.pack("HHHH", session.rows, session.cols, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

        process = await asyncio.create_subprocess_exec(
            *cmd, cwd=session.cwd,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            preexec_fn=os.setsid,
        )
        os.close(slave_fd)

        session._process = process
        session._master_fd = master_fd

    async def _spawn_windows(self, session: TerminalSession) -> None:
        cmd_map = {
            "powershell": ["powershell.exe", "-NoLogo", "-NoExit"],
            "cmd": ["cmd.exe"],
            "bash": ["bash.exe", "--login"],
        }
        cmd = cmd_map.get(session.shell, ["powershell.exe", "-NoLogo", "-NoExit"])

        if HAS_WINPTY:
            pty_proc = WinPtyProcess.spawn(
                cmd,
                cwd=session.cwd,
                dimensions=(session.rows, session.cols),
            )
            session._winpty = pty_proc
            session._process = None
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd, cwd=session.cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            session._process = process


# 글로벌 싱글톤
terminal_manager = TerminalSessionManager()
