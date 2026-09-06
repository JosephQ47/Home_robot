#!/usr/bin/env python3
"""Exercise the task Action lifecycle against ROS-only mocks."""
import os
import signal
import subprocess
import time

from hr_interfaces.action import ExecuteTask
from hr_interfaces.msg import RobotStatus, TaskStatus
from rcl_interfaces.srv import SetParameters
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter


def wait_future(node, future, timeout=8.0):
    end = time.monotonic() + timeout
    while not future.done() and time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
    if not future.done():
        raise RuntimeError('ROS operation timed out')
    return future.result()


def wait_until(node, predicate, timeout=8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
        if predicate():
            return True
    return False


class TaskProbe(Node):
    def __init__(self):
        super().__init__('verify_task_lifecycle')
        self.client = ActionClient(self, ExecuteTask, '/task/execute')
        self.robot = None
        self.task_states = []
        self.create_subscription(RobotStatus, '/robot_status', self._robot, 10)
        self.create_subscription(TaskStatus, '/task/status', self.task_states.append, 20)
        self.parameter_clients = {}

    def _robot(self, msg):
        self.robot = msg

    def set_parameters(self, node_name, values):
        client = self.parameter_clients.get(node_name)
        if client is None:
            client = self.create_client(SetParameters, f'/{node_name}/set_parameters')
            self.parameter_clients[node_name] = client
        if not client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError(f'parameter service unavailable: {node_name}')
        request = SetParameters.Request()
        request.parameters = [Parameter(name, value=value).to_parameter_msg()
                              for name, value in values.items()]
        response = wait_future(self, client.call_async(request))
        if response is None or not all(result.successful for result in response.results):
            raise RuntimeError(f'parameter update failed: {node_name}')

    def send(self, task_id, mode='observe'):
        goal = ExecuteTask.Goal()
        goal.task_id = task_id
        goal.source = 'VALIDATION'
        goal.task_type = 'inspect'
        goal.map_id = 'mock'
        goal.area_id = 'mock'
        goal.target_class = 'person'
        goal.mode = mode
        return wait_future(self, self.client.send_goal_async(goal))

    def result(self, handle, timeout=8.0):
        wrapped = wait_future(self, handle.get_result_async(), timeout)
        return wrapped.result

    def state_code(self, task_id):
        matches = [state.result_code for state in self.task_states if state.task_id == task_id]
        return matches[-1] if matches else ''


def main():
    test_domain = os.environ.get('HR_TEST_ROS_DOMAIN_ID', '66')
    env = os.environ.copy()
    env['ROS_DOMAIN_ID'] = test_domain
    os.environ['ROS_DOMAIN_ID'] = test_domain
    launch = subprocess.Popen(
        ['ros2', 'launch', 'hr_bringup', 'mock.launch.py'], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    rclpy.init()
    node = TaskProbe()
    try:
        if not node.client.wait_for_server(timeout_sec=15.0):
            raise RuntimeError('/task/execute unavailable')
        if not wait_until(node, lambda: node.robot is not None and node.robot.safety_permit):
            raise RuntimeError('safe mock RobotStatus unavailable')

        node.set_parameters('hr_mock_system', {'navigation_delay_sec': 0.2})
        complete = node.send('complete')
        # 把两种失败分开报。合成一条 'normal task did not complete' 时，
        # 下次再挂还是分不清是 goal 没被接受，还是接受了但结果不对。
        if not complete.accepted:
            raise RuntimeError('normal task goal was not accepted')
        outcome = node.result(complete).outcome
        if outcome != 'COMPLETED':
            raise RuntimeError(
                f"normal task ended as {outcome!r} (result_code={node.state_code('complete')!r})")

        node.set_parameters('hr_mock_system', {'navigation_delay_sec': 2.0})
        first = node.send('busy-owner')
        if not first.accepted:
            raise RuntimeError('first busy test task rejected')
        second = node.send('busy-rejected')
        if second.accepted:
            raise RuntimeError('concurrent task was accepted')
        wait_future(node, first.cancel_goal_async())
        if node.result(first).outcome != 'CANCELED':
            raise RuntimeError('task cancellation did not reach CANCELED')

        node.set_parameters('hr_mock_system', {'safety_permit': False})
        if not wait_until(node, lambda: node.robot is not None and not node.robot.safety_permit):
            raise RuntimeError('mock safety state did not change')
        rejected = node.send('precheck-rejected')
        if not rejected.accepted or node.result(rejected).outcome != 'REJECTED':
            raise RuntimeError('unsafe precondition was not rejected')
        if not wait_until(node, lambda: node.state_code('precheck-rejected') == 'SAFETY_NOT_PERMITTED'):
            raise RuntimeError('precondition rejection code missing')

        node.set_parameters('hr_mock_system', {'safety_permit': True, 'remote_override': False})
        if not wait_until(node, lambda: node.robot is not None and node.robot.safety_permit):
            raise RuntimeError('mock safety state did not recover')
        unconfigured = node.send('follow-unconfigured', mode='follow')
        if not unconfigured.accepted or node.result(unconfigured).outcome != 'REJECTED':
            raise RuntimeError('unconfigured follow policy was not rejected')
        if not wait_until(node, lambda: node.state_code('follow-unconfigured') ==
                          'FOLLOW_POLICY_UNCONFIGURED'):
            raise RuntimeError('follow policy rejection code missing')

        node.set_parameters('hr_task_manager', {'task_timeout_sec': 0.3})
        timed_out = node.send('timeout')
        if not timed_out.accepted or node.result(timed_out).outcome != 'TIMED_OUT':
            raise RuntimeError('task timeout did not reach TIMED_OUT')

        node.set_parameters('hr_task_manager', {'task_timeout_sec': 5.0})
        interrupted = node.send('remote-interrupt')
        if not interrupted.accepted:
            raise RuntimeError('remote interrupt task rejected')
        time.sleep(0.2)
        node.set_parameters('hr_mock_system', {'remote_override': True})
        if node.result(interrupted).outcome != 'INTERRUPTED':
            raise RuntimeError('remote takeover did not interrupt task')

        print('PASS: complete, busy reject, precheck reject, cancel, timeout, remote interrupt')
        print('PASS: follow mode stays disabled until explicit safe-distance parameters exist')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        launch.send_signal(signal.SIGINT)
        try:
            output, _ = launch.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(launch.pid, signal.SIGKILL)
            output, _ = launch.communicate()
        if 'Traceback (most recent call last)' in output:
            print(output)
            raise RuntimeError('mock launch did not shut down cleanly')


if __name__ == '__main__':
    main()
