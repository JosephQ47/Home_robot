"""Turns transcripts into ExecuteTask goals, or into a spoken refusal.

Check the ROS graph after starting this: it must have no /cmd_vel publisher and
no servo interface (技术方案 §10.3「语音任务入口」). It only ever acts as an
ExecuteTask action client.

# @spec 家庭服务机器人技术方案.md#3.12.2
"""
from hr_interfaces.action import ExecuteTask
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

from .intent import Intent, Vocabulary, interpret

TASK_TYPES = {'patrol': 'patrol', 'navigate': 'navigate', 'search': 'search',
              'dock': 'dock', 'arm_grasp': 'ARM_GRASP', 'arm_release': 'ARM_RELEASE',
              'arm_home': 'ARM_HOME', 'stop': 'ARM_STOP'}


class VoiceCommandNode(Node):
    def __init__(self):
        super().__init__('hr_voice_command')
        self.declare_parameter('min_confidence', 0.75)
        self.declare_parameter('locations', [''])
        self.declare_parameter('target_classes', [''])
        self.declare_parameter('places', [''])
        self.vocabulary = Vocabulary(
            locations=frozenset(v for v in self.get_parameter('locations').value if v),
            target_classes=frozenset(v for v in self.get_parameter('target_classes').value if v),
            places=frozenset(v for v in self.get_parameter('places').value if v))
        self.feedback = self.create_publisher(String, '/voice/feedback', 10)
        self.audit = self.create_publisher(String, '/voice/transcript', 10)
        self.task = ActionClient(self, ExecuteTask, '/task/execute')
        self.create_subscription(String, '/voice/transcript_in', self.on_transcript, 10)
        self.counter = 0

    def on_transcript(self, msg):
        # The capture node encodes "text|confidence"; a malformed line is refused
        # rather than interpreted at full confidence.
        text, _, raw = msg.data.rpartition('|')
        try:
            confidence = float(raw)
        except ValueError:
            text, confidence = msg.data, 0.0
        result = interpret(text, confidence, self.vocabulary,
                           min_confidence=float(self.get_parameter('min_confidence').value))
        # V-6: both accepted and refused utterances are auditable.
        self.audit.publish(String(data=f'{text}|{confidence}|{result}'))
        if not isinstance(result, Intent):
            if result.spoken:
                self.feedback.publish(String(data=result.spoken))
            return
        self.dispatch(result)

    def dispatch(self, intent):
        task_type = TASK_TYPES.get(intent.intent)
        if task_type is None:
            # report_battery and the gripper commands are answered locally; they
            # are not movement tasks and must not create one.
            self.feedback.publish(String(data='已收到'))
            return
        if not self.task.wait_for_server(timeout_sec=1.0):
            self.feedback.publish(String(data='任务系统未就绪'))
            return
        self.counter += 1
        goal = ExecuteTask.Goal()
        goal.task_id = f'voice-{self.counter}'
        goal.source = 'VOICE'
        goal.task_type = task_type
        goal.target_class = intent.params.get('target_class', '')
        goal.map_id = ''
        goal.area_id = intent.params.get('location', '')
        goal.mode = 'search' if intent.intent == 'search' else ''
        self.task.send_goal_async(goal)


def main(args=None):
    rclpy.init(args=args)
    node = VoiceCommandNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
