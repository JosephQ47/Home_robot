"""docs/images/architecture.svg — the five-layer system architecture.

Reads top to bottom as the command travels: a task becomes a goal, a goal
becomes a velocity, a velocity is vetoed or allowed, and only then does a wheel
turn. Sensing comes back up the right-hand side.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from palette import (INK, LAYERS, LINE, MUTED, MONO, NEW, PANEL, SAFETY,  # noqa: E402
                     arrow_defs, box, header, wrap_text)

W, H = 1240, 1000
LEFT, RIGHT = 32, W - 32
LANE_W = RIGHT - LEFT

# (key, y, height)
BANDS = [('L5', 96, 108), ('L4', 224, 250), ('L3', 494, 104), ('L2', 618, 128), ('L1', 766, 150)]


def node(x, y, w, h, lines, layer, mono_idx=(), badge=None, emphasis=False):
    c = LAYERS[layer]
    parts = [box(x, y, w, h, '#ffffff', c['stroke'], width=2.4 if emphasis else 1.4)]
    total = len(lines)
    start = y + h / 2 - (total - 1) * 7.6 + 4.5
    for i, line in enumerate(lines):
        fam = MONO if i in mono_idx else None
        size = 12.6 if i == 0 else 11.2
        weight = '700' if i == 0 else '400'
        fill = c['text'] if i == 0 else MUTED
        parts += wrap_text(x + w / 2, start + i * 15.2, [line], size, fill,
                           line_height=15.2, weight=weight, family=fam)
    if badge:
        parts.append(f'<rect x="{x + w - 34}" y="{y + 6}" width="28" height="15" rx="7.5" '
                     f'fill="{NEW}"/>')
        parts += wrap_text(x + w - 20, y + 17, [badge], 9.5, '#ffffff', weight='700')
    return parts


def main():
    out = header(W, H, '家庭服务机器人 · 五层系统架构',
                 'RK3588 负责「想去哪」，STM32 决定「现在准不准动」—— 任何自动速度都必须穿过同一条安全链')
    colors = [LAYERS[k]['stroke'] for k in LAYERS] + [SAFETY['stroke'], LINE]
    defs, mk = arrow_defs(colors)
    out = out[:1] + defs + out[1:]

    for key, y, h in BANDS:
        c = LAYERS[key]
        out.append(box(LEFT, y, LANE_W, h, c['fill'], c['stroke'], radius=10, width=1.2))
        out.append(f'<text x="{LEFT + 14}" y="{y + 20}" font-size="12.5" font-weight="700" '
                   f'fill="{c["text"]}">{c["name"]}</text>')

    # ---- L5
    out += node(60, 126, 240, 64, ['任务入口', '定时计划 · 网页 · 语音'], 'L5')
    out += node(340, 126, 250, 64, ['hr_task_manager', '任务仲裁 · 阶段授权 · 互斥'], 'L5', mono_idx={0})
    out += node(630, 126, 250, 64, ['/task/motion_phase', 'NAV · FOLLOW · DOCK · ZERO'], 'L5',
                mono_idx={0})
    out += node(920, 126, 260, 64, ['低电事件', 'SYSTEM_BATTERY 优先回充'], 'L5')

    # ---- L4
    out += node(60, 256, 200, 76, ['Gemini 2 感知', 'RGB · 深度 · 点云'], 'L4')
    out += node(60, 344, 200, 62, ['RPLIDAR S3', '/scan（主环境观测）'], 'L4', mono_idx={1})
    out += node(290, 256, 190, 62, ['hr_perception', 'RKNN YOLO → 检测'], 'L4', mono_idx={0})
    out += node(290, 330, 190, 62, ['hr_depth_obstacle', '地面滤除 · 质量门控'], 'L4',
                mono_idx={0}, badge='NEW')
    out += node(290, 404, 190, 56, ['hr_target_tracker', '深度估距 · 跟随位姿'], 'L4', mono_idx={0})
    out += node(510, 256, 180, 62, ['EKF 融合', 'odom→base_link'], 'L4', mono_idx={1})
    out += node(510, 330, 180, 62, ['SLAM / AMCL', 'map→odom'], 'L4', mono_idx={1})
    out += node(510, 404, 180, 56, ['AprilTag + hr_docking', '/detected_dock_pose'], 'L4',
                mono_idx={1}, badge='NEW')
    out += node(720, 256, 200, 62, ['Nav2', '→ /cmd_vel_nav'], 'L4', mono_idx={1})
    out += node(720, 330, 200, 62, ['OpenNav Docking', '→ /cmd_vel_dock'], 'L4', mono_idx={1})

    # the arbitration + veto pair, visually emphasised: this is the whole point
    out += node(950, 256, 230, 90,
                ['hr_motion_mux', '两路自动速度互斥', '切换先归零 · 过期归零'], 'L4',
                mono_idx={0}, badge='NEW', emphasis=True)
    out.append(box(950, 366, 230, 94, SAFETY['fill'], SAFETY['stroke'], width=2.4))
    out += wrap_text(1065, 396, ['Collision Monitor'], 12.6, SAFETY['text'], weight='700')
    out += wrap_text(1065, 414, ['激光停止区 · 最终否决'], 11.2, SAFETY['text'])
    out += wrap_text(1065, 432, ['唯一 /cmd_vel'], 11.2, SAFETY['text'], family=MONO)

    # ---- L3
    out += node(340, 522, 270, 64, ['hr_bridge', 'CRC16 · Seq · 心跳 · 时间戳'], 'L3', mono_idx={0})
    out += node(660, 522, 270, 64, ['USB-UART 帧协议', '/dev/robot_mcu'], 'L3', mono_idx={1})

    # ---- L2
    out += node(60, 648, 250, 70, ['command_task', '上位机/SBUS 仲裁'], 'L2', mono_idx={0})
    out += node(340, 648, 250, 70, ['chassis_task', '四轮 PI 闭环 · 斜坡限幅'], 'L2', mono_idx={0})
    out += node(620, 648, 250, 70, ['imu_task', 'BMI088 + IST8310'], 'L2', mono_idx={0})
    out.append(box(900, 648, 280, 70, SAFETY['fill'], SAFETY['stroke'], width=2.4))
    out += wrap_text(1040, 676, ['monitor_task'], 12.6, SAFETY['text'], weight='700', family=MONO)
    out += wrap_text(1040, 694, ['安全许可 · 低电分级 · IWDG'], 11.2, SAFETY['text'])

    # ---- L1
    out += node(60, 796, 250, 70, ['4× VNH5019 H 桥', '20 kHz PWM · 过流/堵转'], 'L1')
    out += node(340, 796, 250, 70, ['4× MC520P30 电机', '1560 count/rev 编码器'], 'L1', mono_idx={1})
    out += node(620, 796, 250, 70, ['电池包 + BMS', '总压 · 电流 · 充电状态'], 'L1')
    out += node(900, 796, 280, 70, ['充电桩 + 6轴机械臂', 'AprilTag 导向 · 末端 D435i'], 'L1')

    # ---- sensing feeds planning (thin, so it never competes with the command path)
    blue = LAYERS['L4']['stroke']
    for y0, y1 in ((287, 287), (375, 361)):
        out.append(f'<path d="M 260 {y0} H 290" stroke="{blue}" stroke-width="1.5" '
                   f'fill="none" opacity="0.75" marker-end="url(#{mk[blue]})"/>')
    out.append(f'<path d="M 480 287 H 510" stroke="{blue}" stroke-width="1.5" fill="none" '
               f'opacity="0.75" marker-end="url(#{mk[blue]})"/>')
    out.append(f'<path d="M 480 432 H 510" stroke="{blue}" stroke-width="1.5" fill="none" '
               f'opacity="0.75" marker-end="url(#{mk[blue]})"/>')
    out.append(f'<path d="M 690 287 H 720" stroke="{blue}" stroke-width="1.5" fill="none" '
               f'opacity="0.75" marker-end="url(#{mk[blue]})"/>')
    out.append(f'<path d="M 690 432 H 706 V 361 H 720" stroke="{blue}" stroke-width="1.5" '
               f'fill="none" opacity="0.75" marker-end="url(#{mk[blue]})"/>')

    # ---- task manager authorises the mux; the phase is a renewed permission
    purple = LAYERS['L5']['stroke']
    out.append(f'<path d="M 590 158 H 630" stroke="{purple}" stroke-width="2" fill="none" '
               f'marker-end="url(#{mk[purple]})"/>')
    out.append(f'<path d="M 300 158 H 340" stroke="{purple}" stroke-width="2" fill="none" '
               f'marker-end="url(#{mk[purple]})"/>')
    out.append(f'<path d="M 1050 126 V 112 H 465 V 126" stroke="{purple}" stroke-width="2" '
               f'fill="none" marker-end="url(#{mk[purple]})"/>')
    out.append(f'<path d="M 755 190 V 208 H 1065 V 256" stroke="{purple}" stroke-width="2.2" '
               f'fill="none" marker-end="url(#{mk[purple]})"/>')
    out += wrap_text(900, 204, ['阶段授权（须持续续发，停发即归零）'], 10.5, purple, weight='700')

    # ---- the command path: Nav2 / Docking -> mux -> veto -> bridge -> STM32 -> wheels
    red = SAFETY['stroke']
    out.append(f'<path d="M 920 287 H 950" stroke="{blue}" stroke-width="2.8" fill="none" '
               f'marker-end="url(#{mk[blue]})"/>')
    out.append(f'<path d="M 920 361 H 936 V 310 H 950" stroke="{blue}" stroke-width="2.8" '
               f'fill="none" marker-end="url(#{mk[blue]})"/>')
    out.append(f'<path d="M 1065 346 V 366" stroke="{red}" stroke-width="3.2" fill="none" '
               f'marker-end="url(#{mk[red]})"/>')
    out += wrap_text(1120, 360, ['/cmd_vel_auto'], 10.5, SAFETY['text'], weight='700', family=MONO)
    out.append(f'<path d="M 1065 460 V 492 H 475 V 522" stroke="{red}" stroke-width="3.2" '
               f'fill="none" marker-end="url(#{mk[red]})"/>')
    out += wrap_text(770, 486, ['/cmd_vel（唯一最终速度）'], 11.5, SAFETY['text'],
                     weight='700', family=MONO)
    teal = LAYERS['L3']['stroke']
    out.append(f'<path d="M 610 554 H 660" stroke="{teal}" stroke-width="2.8" fill="none" '
               f'marker-end="url(#{mk[teal]})"/>')
    out.append(f'<path d="M 795 586 V 604 H 185 V 648" stroke="{teal}" stroke-width="2.8" '
               f'fill="none" marker-end="url(#{mk[teal]})"/>')
    orange = LAYERS['L2']['stroke']
    out.append(f'<path d="M 310 683 H 340" stroke="{orange}" stroke-width="2.8" fill="none" '
               f'marker-end="url(#{mk[orange]})"/>')
    out.append(f'<path d="M 400 718 V 730 H 185 V 796" stroke="{orange}" stroke-width="2.8" '
               f'fill="none" marker-end="url(#{mk[orange]})"/>')
    out += wrap_text(268, 772, ['4×PWM / 方向 / 使能'], 10.5, LAYERS['L2']['text'], weight='700')
    grey = LAYERS['L1']['stroke']
    out.append(f'<path d="M 310 820 H 340" stroke="{grey}" stroke-width="2.2" fill="none" '
               f'marker-end="url(#{mk[grey]})"/>')
    out.append(f'<path d="M 340 848 H 310" stroke="{grey}" stroke-width="1.8" fill="none" '
               f'stroke-dasharray="5 4" marker-end="url(#{mk[grey]})"/>')

    # ---- monitor_task's veto, routed under L2 so it crosses nothing
    out.append(f'<path d="M 1000 718 V 748 H 240 V 718" stroke="{red}" stroke-width="2.4" '
               f'fill="none" stroke-dasharray="6 4" marker-end="url(#{mk[red]})"/>')
    out.append(f'<path d="M 520 748 V 718" stroke="{red}" stroke-width="2.4" fill="none" '
               f'stroke-dasharray="6 4" marker-end="url(#{mk[red]})"/>')
    out += wrap_text(700, 764, ['SafetyPermit：安全否决可推翻遥控与自动控制'], 10.5,
                     SAFETY['text'], weight='700')
    # battery and IMU report upward into monitor_task
    out.append(f'<path d="M 800 796 V 782 H 1120 V 718" stroke="{grey}" stroke-width="1.8" '
               f'fill="none" stroke-dasharray="5 4" marker-end="url(#{mk[grey]})"/>')
    out.append(f'<path d="M 870 683 H 900" stroke="{grey}" stroke-width="1.8" fill="none" '
               f'stroke-dasharray="5 4" marker-end="url(#{mk[grey]})"/>')

    # ---- footnote
    out.append(box(LEFT, 930, LANE_W, 48, PANEL, '#d0d7de', radius=8, width=1))
    out += wrap_text(LEFT + 16, 950, ['安全不变量'], 11.5, INK, weight='700', anchor='start')
    out += wrap_text(LEFT + 16, 968,
                     ['① /cmd_vel_auto 的 publisher 有且仅有 hr_motion_mux　'
                      '② 回充速度不得绕过 Collision Monitor　'
                      '③ SBUS 人工接管不依赖上位机存活　'
                      '④ STM32 是限速、限流与执行的唯一权威'],
                     11, MUTED, anchor='start')
    out.append('</svg>')
    dest = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'images' / 'architecture.svg'
    dest.write_text('\n'.join(out), encoding='utf-8')
    print('wrote', dest, len('\n'.join(out)), 'bytes')


if __name__ == '__main__':
    main()
