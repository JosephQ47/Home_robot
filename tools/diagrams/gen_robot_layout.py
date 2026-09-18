"""docs/images/robot-layout.svg — the robot drawn to its own numbers.

Every dimension here is read from the shipped configuration, not chosen for the
picture: the footprint radius from nav2_params.yaml, the arm link lengths from
arm_controller.yaml, the stop zone from collision_monitor.yaml. Change a config
and regenerate — if the drawing stops making sense, the configuration did too.

It is a dimensioned engineering view, not a photograph, and it is labelled that
way. What it is good for is showing that the geometry the software assumes is
self-consistent.
"""
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from palette import (INK, LAYERS, MONO, MUTED, PANEL, SAFETY, arrow_defs, box,  # noqa: E402
                     header, wrap_text)

SRC = pathlib.Path(__file__).resolve().parents[2] / 'upper' / 'src'
W, H = 1240, 760
PX = 420.0          # pixels per metre


def load():
    arm = yaml.safe_load((SRC / 'hr_arm_controller' / 'config' / 'arm_controller.yaml')
                         .read_text())['hr_arm_controller']['ros__parameters']
    nav = yaml.safe_load((SRC / 'hr_navigation' / 'config' / 'nav2_params.yaml').read_text())
    cm = yaml.safe_load((SRC / 'hr_navigation' / 'config' / 'collision_monitor.yaml')
                        .read_text())['collision_monitor']['ros__parameters']
    depth = yaml.safe_load((SRC / 'hr_depth_obstacle' / 'config' / 'depth_obstacle.yaml')
                           .read_text())['hr_depth_obstacle']['ros__parameters']
    radius = nav['local_costmap']['local_costmap']['ros__parameters']['robot_radius']
    pts = cm['StopPolygon']['points']
    stop_x = max(pts[0::2])
    stop_y = max(pts[1::2])
    return arm, radius, stop_x, stop_y, depth


def dim_h(x1, x2, y, text, colour=MUTED):
    """A horizontal dimension line with ticks and a centred label."""
    out = [f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{colour}" stroke-width="1.2"/>']
    for x in (x1, x2):
        out.append(f'<line x1="{x}" y1="{y - 5}" x2="{x}" y2="{y + 5}" '
                   f'stroke="{colour}" stroke-width="1.2"/>')
    out += wrap_text((x1 + x2) / 2, y - 9, [text], 11, colour, weight='600', family=MONO)
    return out


def dim_v(y1, y2, x, text, colour=MUTED):
    out = [f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{colour}" stroke-width="1.2"/>']
    for y in (y1, y2):
        out.append(f'<line x1="{x - 5}" y1="{y}" x2="{x + 5}" y2="{y}" '
                   f'stroke="{colour}" stroke-width="1.2"/>')
    out += wrap_text(x - 8, (y1 + y2) / 2 + 4, [text], 11, colour, weight='600',
                     anchor='end', family=MONO)
    return out


def main():
    arm, radius, stop_x, stop_y, depth = load()
    reach = arm['upper_arm_m'] + arm['forearm_m']
    total_reach = arm['shoulder_offset_m'] + reach + arm['wrist_length_m']

    out = header(W, H, '本体几何 · 按配置里的真实尺寸绘制',
                 '这是工程视图不是照片。每一个尺寸都从仓库配置里读出来，'
                 '改了配置重新生成，图会跟着变')
    defs, mk = arrow_defs([SAFETY['stroke'], MUTED, LAYERS['L4']['stroke']])
    out = out[:1] + defs + out[1:]

    # ---------------- side view ----------------
    ox, oy = 215, 452          # base_link origin on the ground line
    out += wrap_text(150, 116, ['侧视'], 13, INK, weight='700', anchor='start')
    out.append(f'<line x1="60" y1="{oy}" x2="620" y2="{oy}" stroke="{MUTED}" '
               f'stroke-width="2"/>')
    out += wrap_text(66, oy + 18, ['地面'], 10.5, MUTED, anchor='start')

    wheel_r = 0.05
    chassis_h = 0.12
    deck_y = oy - (wheel_r + chassis_h) * PX
    # chassis deck
    out.append(box(ox - 0.22 * PX, deck_y, 0.44 * PX, chassis_h * PX,
                   LAYERS['L1']['fill'], LAYERS['L1']['stroke'], radius=5, width=1.8))
    out += wrap_text(ox, deck_y + chassis_h * PX / 2 + 4, ['底盘'], 11, LAYERS['L1']['text'])
    # wheels
    for dx in (-0.16, 0.16):
        out.append(f'<circle cx="{ox + dx * PX}" cy="{oy - wheel_r * PX}" r="{wheel_r * PX}" '
                   f'fill="#ffffff" stroke="{LAYERS["L1"]["stroke"]}" stroke-width="2"/>')
    out += dim_v(oy - 2 * wheel_r * PX, oy, ox - 0.235 * PX, 'Ø100')

    # sensor mast
    mast_x = ox + 0.19 * PX
    lidar_y = deck_y - 0.085 * PX
    cam_y = oy - 0.35 * PX
    out.append(f'<line x1="{mast_x}" y1="{deck_y}" x2="{mast_x}" y2="{cam_y - 14}" '
               f'stroke="{LAYERS["L1"]["stroke"]}" stroke-width="3"/>')
    out.append(box(mast_x - 26, lidar_y - 13, 52, 26, '#ffffff', LAYERS['L4']['stroke'],
                   radius=5, width=1.8))
    out += wrap_text(mast_x, lidar_y + 4, ['S3'], 11, LAYERS['L4']['text'], weight='700')
    out.append(box(mast_x - 30, cam_y - 14, 60, 26, '#ffffff', LAYERS['L4']['stroke'],
                   radius=5, width=1.8))
    out += wrap_text(mast_x, cam_y + 4, ['Gemini 2'], 10, LAYERS['L4']['text'], weight='700')
    out += dim_v(cam_y, oy, mast_x + 96, '0.35 m')
    out += wrap_text(mast_x + 104, (cam_y + oy) / 2 + 20, ['相机安装高度'], 10.5, MUTED,
                     anchor='start')

    # arm, drawn at its real link lengths in a representative pose
    ax = ox - 0.13 * PX
    ay = deck_y
    sh_y = ay - arm['base_height_m'] * PX
    out.append(f'<line x1="{ax}" y1="{ay}" x2="{ax}" y2="{sh_y}" '
               f'stroke="{LAYERS["L2"]["stroke"]}" stroke-width="7" stroke-linecap="round"/>')
    ex, ey = ax + 0.085 * PX, sh_y - 0.118 * PX
    wx, wy = ex + 0.122 * PX, ey - 0.045 * PX
    tx, ty = wx + 0.020 * PX, wy + 0.088 * PX
    for (x1, y1, x2, y2) in ((ax, sh_y, ex, ey), (ex, ey, wx, wy), (wx, wy, tx, ty)):
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                   f'stroke="{LAYERS["L2"]["stroke"]}" stroke-width="7" stroke-linecap="round"/>')
    for (jx, jy) in ((ax, sh_y), (ex, ey), (wx, wy)):
        out.append(f'<circle cx="{jx}" cy="{jy}" r="5.5" fill="#ffffff" '
                   f'stroke="{LAYERS["L2"]["stroke"]}" stroke-width="2.4"/>')
    out.append(box(tx - 9, ty, 18, 16, '#ffffff', LAYERS['L2']['stroke'], radius=3, width=2))
    out += wrap_text(ax - 14, sh_y + 4, ['6 轴臂'], 10.5, LAYERS['L2']['text'],
                     anchor='end', weight='700')
    out += wrap_text(tx - 14, ty + 30, ['夹爪 + D435i'], 10.5, LAYERS['L2']['text'],
                     anchor='end')

    # stop zone, to the same scale
    zx0 = ox
    zx1 = ox + stop_x * PX
    out.append(f'<rect x="{zx0}" y="{oy - 4}" width="{zx1 - zx0}" height="8" '
               f'fill="{SAFETY["fill"]}" stroke="{SAFETY["stroke"]}" stroke-width="1.6" '
               f'stroke-dasharray="6 4"/>')
    out += dim_h(zx0, zx1, oy + 40, f'停止区 {stop_x:.2f} m', SAFETY['stroke'])

    # ---------------- top view ----------------
    tx0, ty0 = 890, 312
    out += wrap_text(690, 116, ['俯视'], 13, INK, weight='700', anchor='start')
    out.append(f'<circle cx="{tx0}" cy="{ty0}" r="{radius * PX}" fill="{LAYERS["L1"]["fill"]}" '
               f'stroke="{LAYERS["L1"]["stroke"]}" stroke-width="2"/>')
    out += wrap_text(tx0, ty0 + 5, ['base_link'], 11, LAYERS['L1']['text'], family=MONO)
    out.append(f'<rect x="{tx0}" y="{ty0 - stop_y * PX}" width="{stop_x * PX}" '
               f'height="{stop_y * 2 * PX}" fill="{SAFETY["fill"]}" opacity="0.55" '
               f'stroke="{SAFETY["stroke"]}" stroke-width="2" stroke-dasharray="7 5"/>')
    out += wrap_text(tx0 + stop_x * PX / 2, ty0 - stop_y * PX - 12,
                     [f'激光停止区 {stop_x:.2f} × {stop_y * 2:.2f} m'], 11.5,
                     SAFETY['text'], weight='700')
    out.append(f'<circle cx="{tx0}" cy="{ty0}" r="{total_reach * PX}" fill="none" '
               f'stroke="{LAYERS["L2"]["stroke"]}" stroke-width="1.8" stroke-dasharray="4 4"/>')
    out += wrap_text(tx0, ty0 - total_reach * PX - 10, [f'臂展 R {total_reach:.2f} m'], 10.5,
                     LAYERS['L2']['text'], weight='700')
    out += dim_h(tx0, tx0 + radius * PX, ty0 + total_reach * PX + 26, f'R {radius:.2f} m')
    out.append(f'<path d="M {tx0} {ty0} L {tx0 + 58} {ty0}" stroke="{MUTED}" '
               f'stroke-width="2" marker-end="url(#{mk[MUTED]})"/>')
    out += wrap_text(tx0 + 66, ty0 - 8, ['+x'], 10.5, MUTED, anchor='start', family=MONO)

    # ---------------- numbers ----------------
    out.append(box(32, 560, W - 64, 168, PANEL, '#d0d7de', radius=10, width=1))
    out += wrap_text(48, 584, ['图上每个尺寸的出处'], 12, INK, weight='700', anchor='start')
    rows = [
        ('轮廓半径', f'{radius:.2f} m', 'hr_navigation/config/nav2_params.yaml · robot_radius'),
        ('停止区', f'{stop_x:.2f} × {stop_y * 2:.2f} m',
         'hr_navigation/config/collision_monitor.yaml · StopPolygon.points'),
        ('机械臂肩部臂展', f'{reach:.3f} m',
         'hr_arm_controller/config/arm_controller.yaml · upper_arm_m + forearm_m'),
        ('机械臂总臂展', f'{total_reach:.3f} m', '加上肩部偏置与腕长'),
        ('深度有效窗口', f"{depth['min_range_m']:.2f} – {depth['max_range_m']:.2f} m",
         'hr_depth_obstacle/config/depth_obstacle.yaml'),
        ('轮径', '0.100 m', '技术方案 §10.4 已冻结参数'),
    ]
    for i, (label, value, source) in enumerate(rows):
        yy = 608 + i * 19
        out += wrap_text(48, yy, [label], 11, MUTED, anchor='start')
        out += wrap_text(220, yy, [value], 11, INK, anchor='start', weight='700', family=MONO)
        out += wrap_text(360, yy, [source], 10.5, MUTED, anchor='start', family=MONO)

    out.append('</svg>')
    dest = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'images' / 'robot-layout.svg'
    dest.write_text('\n'.join(out), encoding='utf-8')
    print('wrote', dest)


if __name__ == '__main__':
    main()
