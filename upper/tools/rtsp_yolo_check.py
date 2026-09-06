#!/usr/bin/env python3
"""Run the PC ROS image source + YOLO perception chain against a live source.

This script starts only vision nodes. It does not start bridge, navigation,
serial control, or any velocity publisher.
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
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray


def main():
    parser = argparse.ArgumentParser(description='Validate RTSP/UVC/file -> ROS image -> YOLO detections.')
    parser.add_argument('--source', required=True, help='RTSP URL, /dev/videoN, image, video, or synthetic source')
    parser.add_argument('--model', required=True, help='Local YOLO weight path')
    parser.add_argument('--duration', type=float, default=30.0, help='Seconds to observe after nodes start')
    parser.add_argument('--target-class', default='person', help='Class expected for pass/fail')
    parser.add_argument('--confidence', type=float, default=0.35)
    parser.add_argument('--image-size', type=int, default=320)
    parser.add_argument('--inference-hz', type=float, default=2.0)
    parser.add_argument('--publish-hz', type=float, default=8.0)
    parser.add_argument('--output-width', type=int, default=640)
    parser.add_argument('--capture-width', type=int, default=0)
    parser.add_argument('--capture-height', type=int, default=0)
    parser.add_argument('--capture-fps', type=float, default=0.0)
    parser.add_argument('--pixel-format', default='')
    parser.add_argument('--require-detection', action='store_true', help='Exit nonzero if target class is not detected')
    parser.add_argument('--log-dir', default='', help='Keep node logs in this directory')
    args = parser.parse_args()

    if not Path(args.model).is_file():
        raise SystemExit(f'model not found: {args.model}')

    rclpy.init()
    node = rclpy.create_node('rtsp_yolo_check_probe')
    images = []
    detections = []
    diagnostics = []
    class_counts = {}

    def on_image(msg: Image):
        images.append((time.monotonic(), msg.header, msg.width, msg.height))

    def on_detection(msg: Detection2DArray):
        detections.append((time.monotonic(), msg))
        for det in msg.detections:
            for result in det.results:
                name = result.hypothesis.class_id
                class_counts[name] = class_counts.get(name, 0) + 1

    def on_diag(msg: DiagnosticArray):
        diagnostics.extend(msg.status)

    node.create_subscription(Image, '/camera/image_raw', on_image, qos_profile_sensor_data)
    node.create_subscription(Detection2DArray, '/detections', on_detection, 10)
    node.create_subscription(DiagnosticArray, '/diagnostics', on_diag, 10)

    keep_logs = bool(args.log_dir)
    logs = Path(args.log_dir) if keep_logs else Path(tempfile.mkdtemp(prefix='hr-rtsp-yolo-'))
    logs.mkdir(parents=True, exist_ok=True)
    handles = []
    processes = []

    def start(label, module, parameters):
        # label 只作日志文件名，module 是完整导入路径。
        # 二者分开是因为实现已按技术方案 §9.2 归位：图像源在 hr_camera、
        # 识别在 hr_perception，导入路径不再等于节点标签。
        handle = open(logs / f'{label}.log', 'w+', encoding='utf-8')
        handles.append(handle)
        command = [sys.executable, '-c', f'from {module} import main; main()', '--ros-args']
        for key, value in parameters.items():
            command += ['-p', f'{key}:={value}']
        proc = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT)
        processes.append(proc)
        return proc

    def stop(proc):
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    source_params = {
        'source': args.source,
        'publish_hz': args.publish_hz,
        'output_width': args.output_width,
        'capture_width': args.capture_width,
        'capture_height': args.capture_height,
        'capture_fps': args.capture_fps,
    }
    if args.pixel_format:
        source_params['pixel_format'] = args.pixel_format
    perception_params = {
        'model': args.model,
        'classes': [args.target_class],
        'confidence': args.confidence,
        'image_size': args.image_size,
        'inference_hz': args.inference_hz,
    }

    started = time.monotonic()
    velocity_topics_present = []
    try:
        start('perception', 'hr_perception.perception', perception_params)
        start('source', 'hr_camera.source', source_params)
        end = started + args.duration
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.1)
            for proc in processes:
                if proc.poll() is not None:
                    raise RuntimeError(f'node exited early with code {proc.returncode}')
        velocity_topics_present = [name for name, _ in node.get_topic_names_and_types()
                                   if name in ('/cmd_vel', '/cmd_vel_auto')]
    except Exception as exc:
        for handle in handles:
            handle.flush()
            handle.seek(0)
            print(f'--- {handle.name} ---', file=sys.stderr)
            print(handle.read()[-6000:], file=sys.stderr)
        raise
    finally:
        for proc in reversed(processes):
            stop(proc)
        for handle in handles:
            handle.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    elapsed = max(0.001, time.monotonic() - started)
    def diag_level(value):
        if isinstance(value, (bytes, bytearray)):
            return value[0] if value else 0
        return int(value)

    source_diag = [dict((v.key, v.value) for v in s.values) | {'level': diag_level(s.level), 'message': s.message}
                   for s in diagnostics if s.name == 'hr_image_source']
    perception_diag = [dict((v.key, v.value) for v in s.values) | {'level': diag_level(s.level), 'message': s.message}
                       for s in diagnostics if s.name == 'hr_perception']
    target_hits = class_counts.get(args.target_class, 0)
    result = {
        'result': 'PASS' if (images and (target_hits or not args.require_detection)) else 'FAIL',
        'source': args.source if '://' not in args.source else args.source.split('://', 1)[0] + '://<redacted-host-and-path>',
        'elapsed_s': round(elapsed, 2),
        'images': len(images),
        'image_rate_hz': round(len(images) / elapsed, 2),
        'detection_messages': len(detections),
        'class_counts': class_counts,
        'target_class': args.target_class,
        'target_hits': target_hits,
        'latest_image_size': {'width': images[-1][2], 'height': images[-1][3]} if images else None,
        'latest_source_diagnostic': source_diag[-1] if source_diag else {},
        'latest_perception_diagnostic': perception_diag[-1] if perception_diag else {},
        'logs': str(logs) if keep_logs else '(temporary logs removed after process exit)',
        'velocity_topics_present': velocity_topics_present,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['result'] != 'PASS' or result['velocity_topics_present']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
