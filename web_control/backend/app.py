"""HTTP/WebSocket backend for the HomeRobot web console.

This service is intentionally small and dependency-free so it can run on the
RK3588 during early integration. The ROS 2 boundary is isolated behind
TaskAdapter; replace MockTaskAdapter with an rclpy Action Client adapter when
hr_interfaces is available on the target system.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import signal
import socket
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "index.html"

MAPS = {
    "home1": {"id": "home1", "name": "住宅一层", "meta": "一层住宅 · 2026-08-28 更新"},
    "home2": {"id": "home2", "name": "住宅二层", "meta": "二层住宅 · 2026-08-25 更新"},
    "lab": {"id": "lab", "name": "调试场地", "meta": "研发实验室 · 2026-08-31 更新"},
}

AREAS = {
    "living": {"id": "living", "name": "客厅", "map_ids": ["home1"]},
    "kitchen": {"id": "kitchen", "name": "厨房", "map_ids": ["home1"]},
    "corridor": {"id": "corridor", "name": "走廊", "map_ids": ["home1", "home2", "lab"]},
    "bedroom": {"id": "bedroom", "name": "卧室", "map_ids": ["home1", "home2"]},
    "study": {"id": "study", "name": "书房", "map_ids": ["home1", "home2"]},
}

TARGETS = {
    "人员": {"name": "人员", "trackable": True},
    "纸箱": {"name": "纸箱", "trackable": True},
    "垃圾桶": {"name": "垃圾桶", "trackable": True},
    "杯子": {"name": "杯子", "trackable": False},
}

MODES = {"search": "搜索", "follow": "跟随", "observe": "仅观察"}


@dataclass
class Task:
    task_id: str
    request_id: str
    name: str
    map_id: str
    area_id: str
    target_class: str
    mode: str
    source: str = "WEB"
    status: str = "ACCEPTED"
    phase: str = "PRECHECK"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    message: str = "任务已接收，等待 hr_task_manager 前置检查"
    options: dict[str, Any] = field(default_factory=dict)


class TaskAdapter:
    """Boundary for the future ROS 2 ExecuteTask Action Client."""

    def submit(self, task: Task) -> Task:
        raise NotImplementedError

    def cancel(self, task: Task, reason: str) -> Task:
        raise NotImplementedError


class MockTaskAdapter(TaskAdapter):
    """Local simulator used before ROS 2 is available."""

    def submit(self, task: Task) -> Task:
        task.status = "RUNNING"
        task.phase = "SEARCHING" if task.mode == "search" else task.mode.upper()
        task.message = "模拟后端已创建任务；真机部署时这里会转发为 /task/execute Goal"
        task.updated_at = time.time()
        return task

    def cancel(self, task: Task, reason: str) -> Task:
        task.status = "CANCELLED"
        task.phase = "CANCELLED"
        task.message = reason or "用户通过网页取消任务"
        task.updated_at = time.time()
        return task


class RobotState:
    def __init__(self, adapter: TaskAdapter) -> None:
        self._adapter = adapter
        self._lock = threading.RLock()
        self._tasks: list[Task] = [
            Task(
                task_id="task-001",
                request_id="seed-001",
                name="晚间巡检",
                map_id="home1",
                area_id="corridor",
                target_class="人员",
                mode="search",
                status="DONE",
                phase="DONE",
                message="模拟历史任务已完成",
            ),
            Task(
                task_id="task-002",
                request_id="seed-002",
                name="垃圾桶观察",
                map_id="home1",
                area_id="kitchen",
                target_class="垃圾桶",
                mode="observe",
                status="ACCEPTED",
                phase="PRECHECK",
                message="等待任务准入检查",
            ),
        ]
        self._wifi = "Home_5G"
        self._started_at = time.time()

    def bootstrap(self) -> dict[str, Any]:
        with self._lock:
            return {
                "maps": list(MAPS.values()),
                "areas": list(AREAS.values()),
                "targets": list(TARGETS.values()),
                "modes": [{"id": key, "name": value} for key, value in MODES.items()],
                "system": self.system_status(),
                "tasks": [self._task_view(task) for task in self._tasks],
                "wifi": {
                    "current": self._wifi,
                    "networks": [
                        {"ssid": "Home_5G", "security": "WPA2", "signal": "high"},
                        {"ssid": "Home_2.4G", "security": "WPA2", "signal": "medium"},
                        {"ssid": "RobotLab", "security": "WPA3", "signal": "high"},
                        {"ssid": "Guest", "security": "OPEN", "signal": "low"},
                    ],
                },
                "logs": self.logs(),
            }

    def system_status(self) -> dict[str, Any]:
        active = next((task for task in self._tasks if task.status == "RUNNING"), None)
        return {
            "robot_online": True,
            "battery_percent": 78,
            "localization": "AMCL 已定位",
            "safety": "雷达避障已启用",
            "control_source": "AUTO",
            "uptime_seconds": int(time.time() - self._started_at),
            "active_task_id": active.task_id if active else None,
        }

    def logs(self) -> list[dict[str, str]]:
        return [
            {"time": "10:21:08", "level": "INFO", "message": "hr_task_manager：任务进入搜索点"},
            {"time": "10:21:12", "level": "INFO", "message": "hr_target_tracker：目标关联有效"},
            {"time": "10:21:13", "level": "WARN", "message": "目标短时遮挡，保持零速等待重新锁定"},
            {"time": "10:21:14", "level": "INFO", "message": "目标重新锁定，恢复局部跟随"},
        ]

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            request_id = str(payload.get("request_id") or payload.get("client_request_id") or "")
            if request_id:
                existing = next((task for task in self._tasks if task.request_id == request_id), None)
                if existing:
                    return self._task_view(existing)

            task = self._build_task(payload, request_id or str(uuid.uuid4()))
            active = next((item for item in self._tasks if item.status == "RUNNING"), None)
            if active:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "TASK_BUSY",
                    f"当前已有活动任务 {active.task_id}，网页任务不在后台堆积等待",
                )

            submitted = self._adapter.submit(task)
            self._tasks.insert(0, submitted)
            return self._task_view(submitted)

    def cancel_task(self, task_id: str, reason: str) -> dict[str, Any]:
        with self._lock:
            task = self._find_task(task_id)
            if task.status in {"CANCELLED", "DONE", "FAILED", "REJECTED"}:
                return self._task_view(task)
            return self._task_view(self._adapter.cancel(task, reason))

    def delete_task(self, task_id: str) -> dict[str, str]:
        with self._lock:
            task = self._find_task(task_id)
            if task.status == "RUNNING":
                self._adapter.cancel(task, "删除前先取消任务")
            self._tasks = [item for item in self._tasks if item.task_id != task_id]
            return {"task_id": task_id, "status": "DELETED"}

    def set_wifi(self, ssid: str) -> dict[str, str]:
        if not ssid:
            raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_WIFI", "SSID 不能为空")
        with self._lock:
            self._wifi = ssid
            return {"current": self._wifi}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "type": "status",
                "system": self.system_status(),
                "tasks": [self._task_view(task) for task in self._tasks],
                "wifi": {"current": self._wifi},
                "ts": time.time(),
            }

    def _build_task(self, payload: dict[str, Any], request_id: str) -> Task:
        map_id = str(payload.get("map_id") or payload.get("map") or "")
        area_id = str(payload.get("area_id") or payload.get("area") or "")
        target_class = str(payload.get("target_class") or payload.get("target") or "")
        mode = str(payload.get("mode") or "")

        if map_id not in MAPS:
            raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_MAP", "地图不存在或未验收")
        if area_id not in AREAS or map_id not in AREAS[area_id]["map_ids"]:
            raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_AREA", "区域不属于当前地图或未验收")
        if target_class not in TARGETS:
            raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_TARGET", "目标类别不支持")
        if mode not in MODES:
            raise ApiError(HTTPStatus.BAD_REQUEST, "INVALID_MODE", "任务模式不支持")
        if mode == "follow" and not TARGETS[target_class]["trackable"]:
            raise ApiError(HTTPStatus.BAD_REQUEST, "TARGET_NOT_TRACKABLE", "该目标无可靠雷达关联，不能进入跟随")

        name = str(payload.get("name") or f"{AREAS[area_id]['name']}目标任务")[:30]
        return Task(
            task_id=f"web-{uuid.uuid4().hex[:10]}",
            request_id=request_id,
            name=name,
            map_id=map_id,
            area_id=area_id,
            target_class=target_class,
            mode=mode,
            options={
                "distance_policy": payload.get("distance_policy"),
                "speed_policy": payload.get("speed_policy"),
            },
        )

    def _find_task(self, task_id: str) -> Task:
        task = next((item for item in self._tasks if item.task_id == task_id), None)
        if not task:
            raise ApiError(HTTPStatus.NOT_FOUND, "TASK_NOT_FOUND", "任务不存在")
        return task

    def _task_view(self, task: Task) -> dict[str, Any]:
        item = asdict(task)
        item["map_name"] = MAPS[task.map_id]["name"]
        item["area_name"] = AREAS[task.area_id]["name"]
        item["mode_name"] = MODES[task.mode]
        return item


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class HomeRobotHandler(BaseHTTPRequestHandler):
    server_version = "HomeRobotWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            self._send_json(self.server.state.bootstrap())
        elif parsed.path == "/api/status":
            self._send_json(self.server.state.snapshot())
        elif parsed.path == "/ws/status":
            self._handle_websocket()
        else:
            self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/tasks":
                self._send_json(self.server.state.create_task(payload), HTTPStatus.CREATED)
            elif parsed.path.endswith("/cancel") and parsed.path.startswith("/api/tasks/"):
                task_id = parsed.path.split("/")[3]
                reason = str(payload.get("reason") or "用户通过网页取消任务")
                self._send_json(self.server.state.cancel_task(task_id, reason))
            elif parsed.path == "/api/wifi/connect":
                self._send_json(self.server.state.set_wifi(str(payload.get("ssid") or "")))
            else:
                raise ApiError(HTTPStatus.NOT_FOUND, "NOT_FOUND", "接口不存在")
        except ApiError as exc:
            self._send_error(exc.status, exc.code, exc.message)
        except json.JSONDecodeError:
            self._send_error(HTTPStatus.BAD_REQUEST, "BAD_JSON", "请求体不是合法 JSON")

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/tasks/"):
            task_id = parsed.path.split("/")[3]
            try:
                self._send_json(self.server.state.delete_task(task_id))
            except ApiError as exc:
                self._send_error(exc.status, exc.code, exc.message)
        else:
            self._send_error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "接口不存在")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json({"error": {"code": code, "message": message}}, status)

    def _serve_static(self, path: str) -> None:
        target = INDEX_HTML if path in {"", "/"} else ROOT / path.lstrip("/")
        if not target.exists() or not target.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "文件不存在")
            return
        content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "application/octet-stream"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_websocket(self) -> None:
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self._send_error(HTTPStatus.BAD_REQUEST, "BAD_WEBSOCKET", "缺少 WebSocket 握手头")
            return

        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        self.connection.settimeout(0.2)
        while self.server.running:
            try:
                self._send_ws_text(json.dumps(self.server.state.snapshot(), ensure_ascii=False))
                time.sleep(1.0)
                try:
                    data = self.connection.recv(2)
                    if not data or data[0] & 0x0F == 0x8:
                        break
                except socket.timeout:
                    pass
            except (BrokenPipeError, ConnectionResetError, OSError):
                break

    def _send_ws_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        if len(payload) < 126:
            header.append(len(payload))
        elif len(payload) < 65536:
            header.extend([126, (len(payload) >> 8) & 0xFF, len(payload) & 0xFF])
        else:
            header.extend(
                [
                    127,
                    (len(payload) >> 56) & 0xFF,
                    (len(payload) >> 48) & 0xFF,
                    (len(payload) >> 40) & 0xFF,
                    (len(payload) >> 32) & 0xFF,
                    (len(payload) >> 24) & 0xFF,
                    (len(payload) >> 16) & 0xFF,
                    (len(payload) >> 8) & 0xFF,
                    len(payload) & 0xFF,
                ]
            )
        self.connection.sendall(header + payload)


class HomeRobotServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], state: RobotState) -> None:
        super().__init__(address, HomeRobotHandler)
        self.state = state
        self.running = True


def run(host: str, port: int) -> None:
    server = HomeRobotServer((host, port), RobotState(MockTaskAdapter()))

    def stop(_signum: int, _frame: Any) -> None:
        server.running = False
        server.shutdown()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(f"HomeRobot web backend listening on http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="HomeRobot web UI backend")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":
    main()
