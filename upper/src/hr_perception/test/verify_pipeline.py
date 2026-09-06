"""Opt-in integration check using real weights and a person-containing image.

Run in an unused ROS_DOMAIN_ID with vision_env.sh sourced.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

import rclpy
from diagnostic_msgs.msg import DiagnosticArray
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray
from rclpy.qos import qos_profile_sensor_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    rclpy.init()
    node = rclpy.create_node('vision_acceptance_probe')
    seen, images, diagnostics = [], [], []
    node.create_subscription(Detection2DArray, '/detections',
                             lambda msg: seen.append((time.monotonic(), msg)), 10)
    node.create_subscription(Image, '/camera/image_raw', lambda msg: images.append(msg.header),
                             qos_profile_sensor_data)
    node.create_subscription(DiagnosticArray, '/diagnostics',
                             lambda msg: diagnostics.extend(msg.status), 10)
    processes = []
    logs = tempfile.TemporaryDirectory(prefix='hr-vision-check-')
    handles = []

    def start(module, parameters):
        output = open(Path(logs.name) / f'{module}-{len(processes)}.log', 'w+')
        handles.append(output)
        command = [sys.executable, '-c', f'from hr_perception.{module} import main; main()', '--ros-args']
        for key, value in parameters.items():
            command += ['-p', f'{key}:={value}']
        proc = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
        processes.append(proc)
        return proc

    def stop(proc):
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def until(predicate, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.1)
            if predicate():
                return
        raise AssertionError('timed out waiting for pipeline state')

    def has_person(since=0):
        return any(t >= since and any(h.hypothesis.class_id == 'person'
                   for d in msg.detections for h in d.results) for t, msg in seen)

    try:
        perception = start('perception', {'model': args.model})
        source = start('source', {'source': args.image})
        # BEST_EFFORT image subscribers can drop different frames independently.
        # Wait for an observed matching pair instead of assuming the probe saw
        # the first frame which reached the inference subscriber.
        until(lambda: has_person() and any(msg.detections and msg.header in images
                                           for _, msg in seen), 60)
        assert perception.poll() is None
        valid = next(msg for _, msg in seen if msg.detections and msg.header in images)
        assert valid.header in images, 'detection must retain the source image header'
        assert not any(name in ('/cmd_vel', '/cmd_vel_auto') for name, _ in node.get_topic_names_and_types())
        stop(source)
        stopped = time.monotonic()
        until(lambda: any(t > stopped and not msg.detections for t, msg in seen), 8)
        # A delayed old image must not reactivate detections.
        injected = Image(height=1, width=1, encoding='bgr8', step=3, data=[0, 0, 0])
        injected.header.stamp.sec = 1
        pub = node.create_publisher(Image, '/camera/image_raw', qos_profile_sensor_data)
        for _ in range(10):
            pub.publish(injected)
            rclpy.spin_once(node, timeout_sec=.1)
        cutoff = time.monotonic()
        end = cutoff + 3
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.1)
        assert not has_person(cutoff), 'old image resurrected a valid detection'
        restarted = time.monotonic()
        source = start('source', {'source': args.image})
        until(lambda: has_person(restarted), 15)
        values = [dict((v.key, v.value) for v in status.values)
                  for status in diagnostics if status.name == 'hr_perception']
        print(json.dumps({'result': 'PASS', 'images': len(images), 'detection_messages': len(seen),
                          'person_detected': True, 'source_stop_invalidated': True,
                          'old_frame_rejected': True, 'source_restart_recovered': True,
                          'latest_perception_diagnostic': values[-1] if values else {}}, indent=2))
    except Exception:
        for handle in handles:
            handle.flush()
            handle.seek(0)
            print(handle.read()[-6000:], file=sys.stderr)
        raise
    finally:
        for proc in reversed(processes):
            stop(proc)
        for handle in handles:
            handle.close()
        logs.cleanup()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
