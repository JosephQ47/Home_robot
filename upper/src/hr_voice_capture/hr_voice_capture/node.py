"""Wake word and speech capture. Skeleton: microphone not selected.

Publishes transcripts with confidence for hr_voice_command to interpret. The
ASR engine sits behind a replaceable adapter, so this package does not bind the
project to a particular engine.

# @spec 家庭服务机器人技术方案.md#3.12.2
"""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class VoiceCaptureNode(Node):
    def __init__(self):
        super().__init__('hr_voice_capture')
        self.declare_parameter('device', '')
        self.declare_parameter('asr_adapter', '')
        if not str(self.get_parameter('asr_adapter').value):
            raise RuntimeError('hr_voice_capture needs an asr_adapter; none is frozen yet')
        raise RuntimeError('hr_voice_capture is a skeleton: no microphone is fitted')


def main(args=None):
    rclpy.init(args=args)
    try:
        node = VoiceCaptureNode()
    except RuntimeError:
        rclpy.shutdown()
        raise
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
