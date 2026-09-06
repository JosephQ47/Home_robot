"""Threaded rclpy adapter implementing web_control's TaskAdapter contract."""
import json
import threading
import time

from hr_interfaces.action import ExecuteTask
from hr_interfaces.msg import RobotStatus
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node


class RosTaskAdapter:
    is_mock = False

    def __init__(self, response_timeout=5.0):
        if not rclpy.ok(): rclpy.init()
        self.node = Node('hr_web_action_adapter')
        self.client = ActionClient(self.node, ExecuteTask, '/task/execute')
        self.executor = MultiThreadedExecutor(num_threads=2); self.executor.add_node(self.node)
        self.thread = threading.Thread(target=self.executor.spin, daemon=True); self.thread.start()
        self.timeout = response_timeout; self.handles = {}; self.tasks = {}
        self.robot_status = None; self.robot_status_time = 0.0
        self.subscription = self.node.create_subscription(RobotStatus, '/robot_status', self._robot_status, 10)

    def submit(self, task):
        if not self.client.wait_for_server(timeout_sec=self.timeout):
            raise RuntimeError('/task/execute is unavailable')
        goal = ExecuteTask.Goal()
        goal.task_id, goal.source = task.task_id, task.source
        goal.task_type, goal.map_id, goal.area_id = task.mode, task.map_id, task.area_id
        goal.target_class, goal.mode = task.target_class, task.mode
        goal.options_json = json.dumps(task.options, ensure_ascii=False)
        done = threading.Event(); response = {}
        future = self.client.send_goal_async(goal, feedback_callback=lambda msg: self._feedback(task, msg))
        future.add_done_callback(lambda result: (response.setdefault('handle', result.result()), done.set()))
        if not done.wait(self.timeout): raise RuntimeError('task action acceptance timed out')
        handle = response['handle']
        if not handle.accepted: raise RuntimeError('task rejected as busy')
        self.handles[task.task_id] = handle; self.tasks[task.task_id] = task
        task.status, task.phase, task.message = 'ACCEPTED', 'PRECHECK', 'ROS task accepted'
        result = handle.get_result_async(); result.add_done_callback(lambda value: self._result(task, value.result().result))
        return task

    def cancel(self, task, reason):
        handle = self.handles.get(task.task_id)
        if handle is not None: handle.cancel_goal_async()
        task.status, task.phase, task.message = 'CANCELLED', 'CANCELING', reason or 'web cancel requested'
        return task

    def _feedback(self, task, message):
        status = message.feedback.status
        task.status, task.phase, task.message = status.status, status.stage, status.message

    def _result(self, task, result):
        task.status = 'DONE' if result.success else result.outcome
        task.phase = 'DONE' if result.success else 'ZERO'
        task.message = result.message
        self.handles.pop(task.task_id, None)

    def _robot_status(self, message):
        self.robot_status = message
        self.robot_status_time = time.monotonic()

    def system_status(self):
        status = self.robot_status
        online = status is not None and time.monotonic() - self.robot_status_time < 2.0
        source = {RobotStatus.CONTROL_AUTO: 'AUTO', RobotStatus.CONTROL_REMOTE: 'REMOTE',
                  RobotStatus.CONTROL_SAFE_STOP: 'SAFE_STOP'}.get(status.control_source if status else 0, 'UNKNOWN')
        return {'robot_online': online,
                'battery_percent': status.battery_percent if online else None,
                'localization': '未接入定位状态',
                'safety': '允许' if online and status.safety_permit else '禁止',
                'control_source': source,
                'uptime_seconds': None,
                'active_task_id': next(iter(self.handles), None)}

    def close(self):
        self.executor.shutdown(timeout_sec=2.0)
        self.node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
