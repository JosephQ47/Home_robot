#!/usr/bin/env python3
"""HMMD 毫米波：串口连通性自检 + 目标距离字段标定采集。

为什么需要标定
--------------
hr_hmmd 的 range_scale_m 默认是 0.0，此时 range_m 发 NaN、valid=false ——
这是刻意的：官方说「一个距离门 0.7 m」，但**目标距离字段的单位不等于 0.7 m**，
没实测前不许猜。跟随链的最小安全距离判定依赖这个标度，猜错的后果是机器人
以为还有 2 m 其实只有 0.5 m。

用法
----
  # 1. 先自检：确认串口有数据、帧能解析
  python3 upper/tools/hmmd_calibrate.py --probe

  # 2. 三点采样：人站在已用卷尺量好的距离上，各采一次
  python3 upper/tools/hmmd_calibrate.py --sample 1.0
  python3 upper/tools/hmmd_calibrate.py --sample 2.0
  python3 upper/tools/hmmd_calibrate.py --sample 3.0

  # 3. 拟合出标度
  python3 upper/tools/hmmd_calibrate.py --fit

本脚本只读写 HMMD 的串口，不发布任何 ROS 话题，不碰 /dev/ttyACM0（下位机）。
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros2_ws/src/hr_hmmd'))
sys.path.insert(0, '/home/luckfox/.local/lib/python3.10/site-packages')

import serial  # noqa: E402
from hr_hmmd.protocol import Parser, REPORT_MODE_COMMAND  # noqa: E402

DEFAULT_PORT = '/dev/ttyACM3'
SAMPLES = Path(__file__).resolve().parent / 'hmmd_calibration_samples.json'
LOWER_MCU = '/dev/ttyACM0'


def open_port(port, baud, configure):
    if port == LOWER_MCU:
        raise SystemExit(f'拒绝打开 {LOWER_MCU}：那是下位机，不是 HMMD')
    s = serial.Serial(port, baud, timeout=0.1)
    s.reset_input_buffer()
    if configure:
        s.write(REPORT_MODE_COMMAND)
        s.flush()
        time.sleep(0.3)
        s.reset_input_buffer()
    return s


def collect(port, baud, seconds, configure=True):
    """返回 (detections, 原始字节数)。"""
    s = open_port(port, baud, configure)
    parser = Parser()
    dets = []
    total = 0
    try:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            chunk = s.read(4096)
            if chunk:
                total += len(chunk)
                dets.extend(parser.feed(chunk))
    finally:
        s.close()
    return dets, total, parser.bad_frames


def cmd_probe(args):
    print(f'读取 {args.port} @ {args.baud}，{args.seconds} 秒 …')
    dets, total, bad = collect(args.port, args.baud, args.seconds, not args.no_configure)
    print(f'原始字节 {total}｜解析帧 {len(dets)}｜坏帧 {bad}')
    if total == 0:
        print('\n收到 0 字节。按可能性从高到低排查：')
        print('  1. 模块没供电 —— USB 转串口芯片自己有 USB 供电会正常枚举，')
        print('     这掩盖了后面模块没电的事实。先量 VCC 上有没有 3.3 V。')
        print('  2. TX/RX 接反 —— 模块 TX 接转接板 RX，模块 RX 接转接板 TX。')
        print('  3. 接错口 —— 用 /dev/serial/by-id/ 确认，别认 ttyACM 编号。')
        print('  4. 电平不对 —— 必须 3.3 V TTL；5 V 或 RS-232 会烧模块。')
        return 1
    if not dets:
        print('\n有字节但解析不出帧：波特率可能不对，或模块不在上报模式。')
        return 1
    ranges = [d.range_raw for d in dets]
    presence = sum(d.presence for d in dets)
    print(f'\n有人帧 {presence}/{len(dets)}')
    print(f'range_raw: 最小 {min(ranges)}  最大 {max(ranges)}  中位 {statistics.median(ranges):.0f}')
    print(f'速率约 {len(dets)/args.seconds:.1f} Hz（官方标称 10 Hz）')
    print('\n自检通过。下一步做三点采样：--sample 1.0 / 2.0 / 3.0')
    return 0


def cmd_sample(args):
    truth = args.sample
    print(f'请让被测目标站在距模块 {truth} m 处（卷尺量准，站定别动）。')
    for i in (3, 2, 1):
        print(f'  {i} …', flush=True)
        time.sleep(1)
    print(f'采集 {args.seconds} 秒 …')
    dets, total, bad = collect(args.port, args.baud, args.seconds, not args.no_configure)
    live = [d.range_raw for d in dets if d.presence]
    if not live:
        print(f'没采到「有人」的帧（原始字节 {total}，帧 {len(dets)}，坏帧 {bad}）。')
        print('HMMD 只对运动/微动人体有反应，纯静止不上报 —— 让人轻微晃动。')
        return 1
    med = statistics.median(live)
    spread = (max(live) - min(live)) / 2
    print(f'有人帧 {len(live)}/{len(dets)}｜range_raw 中位 {med:.0f}｜半幅 ±{spread:.0f}')
    data = json.loads(SAMPLES.read_text()) if SAMPLES.exists() else {}
    data[str(truth)] = {'truth_m': truth, 'range_raw_median': med,
                        'range_raw_spread': spread, 'n': len(live),
                        'captured_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    SAMPLES.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f'已写入 {SAMPLES.name}（当前 {len(data)} 个采样点）')
    return 0


def cmd_fit(args):
    if not SAMPLES.exists():
        print('还没有采样数据，先跑 --sample')
        return 1
    data = json.loads(SAMPLES.read_text())
    pts = sorted(((v['truth_m'], v['range_raw_median']) for v in data.values()))
    if len(pts) < 2:
        print(f'只有 {len(pts)} 个点，至少要 2 个（建议 3 个）')
        return 1
    print('采样点：')
    for t, r in pts:
        print(f'  真值 {t:.2f} m  ←  range_raw {r:.0f}')
    # 过原点的最小二乘：range_m = scale * range_raw
    num = sum(t * r for t, r in pts)
    den = sum(r * r for t, r in pts)
    if den == 0:
        print('range_raw 全为 0，无法拟合')
        return 1
    scale = num / den
    print(f'\n过原点拟合：range_scale_m = {scale:.6f}  （即 1 count ≈ {scale*1000:.2f} mm）')
    print('残差：')
    worst = 0.0
    for t, r in pts:
        err = scale * r - t
        worst = max(worst, abs(err))
        print(f'  {t:.2f} m → 预测 {scale*r:.3f} m，误差 {err*100:+.1f} cm')
    print(f'\n最大误差 {worst*100:.1f} cm')
    if worst > 0.15:
        print('⚠️ 误差超过 15 cm。官方明说本模块「不建议用作精准测距」，')
        print('   若线性拟合不住，就不要把它当距离传感器用，只当「远/近」阈值。')
    print(f'\n写入 hr_hmmd 配置：range_scale_m: {scale:.6f}')
    print('位置：upper/ros2_ws/src/hr_hmmd/config/hmmd.yaml')
    print('改完必须重新 colcon build 并 source，否则跑的还是旧参数。')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', default=DEFAULT_PORT)
    ap.add_argument('--baud', type=int, default=115200)
    ap.add_argument('--seconds', type=float, default=8.0)
    ap.add_argument('--no-configure', action='store_true',
                    help='不发上报模式命令，纯被动读')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--probe', action='store_true', help='串口连通性自检')
    g.add_argument('--sample', type=float, metavar='米', help='在该真值距离采一个点')
    g.add_argument('--fit', action='store_true', help='用已采样点拟合标度')
    args = ap.parse_args()
    if args.probe:
        return cmd_probe(args)
    if args.sample is not None:
        return cmd_sample(args)
    return cmd_fit(args)


if __name__ == '__main__':
    sys.exit(main())
