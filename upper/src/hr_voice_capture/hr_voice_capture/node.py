"""Wake word + speech capture. Publishes transcripts for hr_voice_command.

It recognises and forwards; it decides nothing. Every utterance goes out with
its confidence attached so the downstream mapper can refuse a weak one, and
nothing here ever publishes a velocity or a servo command.

# @spec 家庭服务机器人技术方案.md#3.12.2
"""
import time

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

from .asr import TextAdapter, WakeWordGate, make_adapter


class VoiceCaptureNode(Node):
    def __init__(self):
        super().__init__('hr_voice_capture')
        self.declare_parameter('asr_adapter', 'text')
        self.declare_parameter('model_path', '')
        self.declare_parameter('device', '')
        self.declare_parameter('wake_word', '')
        self.declare_parameter('wake_window_sec', 8.0)
        self.declare_parameter('poll_rate_hz', 10.0)

        device = str(self.get_parameter('device').value) or None
        self.adapter = make_adapter(str(self.get_parameter('asr_adapter').value),
                                    str(self.get_parameter('model_path').value),
                                    device, self.get_logger())
        self.gate = WakeWordGate(str(self.get_parameter('wake_word').value),
                                 float(self.get_parameter('wake_window_sec').value))
        if not self.gate.wake_word:
            self.get_logger().warning(
                'no wake_word configured: every recognised sentence is treated as '
                'a command candidate. Acceptable on a bench, not on a robot.')

        self.pub = self.create_publisher(String, '/voice/transcript_in', 10)
        self.diag = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        if isinstance(self.adapter, TextAdapter):
            # Lets a PC run drive the whole voice chain with `ros2 topic pub`.
            self.create_subscription(String, '/voice/text_in',
                                     lambda m: self.adapter.submit(m.data), 10)
        self.heard = 0
        self.gated = 0
        rate = float(self.get_parameter('poll_rate_hz').value)
        if rate <= 0.0:
            raise ValueError('poll_rate_hz must be positive')
        self.create_timer(1.0 / rate, self.poll)
        self.create_timer(1.0, self.publish_diagnostics)

    def poll(self):
        now = time.monotonic()
        for utterance in self.adapter.poll():
            if not utterance.text:
                continue
            self.heard += 1
            if not self.gate.feed(utterance.text, now):
                self.gated += 1
                continue
            self.gate.close_window()
            self.pub.publish(String(data=f'{utterance.text}|{utterance.confidence}'))

    def publish_diagnostics(self):
        status = DiagnosticStatus(name='hr_voice_capture', hardware_id='microphone')
        status.level = DiagnosticStatus.OK
        status.message = self.adapter.name
        status.values = [
            KeyValue(key='utterances_heard', value=str(self.heard)),
            KeyValue(key='utterances_gated', value=str(self.gated)),
            KeyValue(key='wake_word_configured', value=str(bool(self.gate.wake_word))),
        ]
        array = DiagnosticArray(status=[status])
        array.header.stamp = self.get_clock().now().to_msg()
        self.diag.publish(array)

    def destroy_node(self):
        try:
            self.adapter.close()
        finally:
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = VoiceCaptureNode()
    except (ImportError, ValueError) as exc:
        print(f'hr_voice_capture: {exc}')
        rclpy.shutdown()
        raise SystemExit(1)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
