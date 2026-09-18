"""docs/images/module-status.svg — what actually works, stated plainly.

An honest maturity chart is worth more than a green one. Each row says how far
a module got and what is blocking it, so a reader can tell measured results
apart from code that has only ever run on a desk.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from palette import INK, MONO, MUTED, PANEL, box, esc, header, wrap_text  # noqa: E402

W = 1240

LEVELS = {
    'measured': ('实测通过', '#1a7f37', '#dafbe1'),
    'tested':   ('已实现·有测试', '#1a73e8', '#ddf4ff'),
    'skeleton': ('骨架·逻辑有测试', '#9a6700', '#fff8c5'),
    'config':   ('仅配置', '#57606a', '#eaeef2'),
    'blocked':  ('缺件阻塞', '#cf222e', '#ffebe9'),
}

# (module, level, note, tests)
ROWS = [
    ('STM32 四轮闭环 + 安全链', 'measured', '真实制动 / 急停 / 断链停车 / 过流保护均已实机验收', '—'),
    ('hr_bridge 上下位机协议', 'measured', 'CRC / 序号 / 断链重连实测；/battery_state 待下位机电池帧', '回环·丢帧·乱序'),
    ('hr_motion_mux 速度仲裁', 'tested', '运行时验收 /cmd_vel_auto publisher 恰为 1；待与真实 Nav2 联调', '12 条单元测试'),
    ('hr_task_manager 任务编排', 'tested', '已支持 DOCKING 阶段与授权续发；低电回充分支待电池数据', '生命周期测试'),
    ('hr_web_ui 网页控制台', 'tested', '前后端跑通，Mock / ROS 双适配器', '后端单元测试'),
    ('hr_perception 视觉识别', 'tested', 'CPU YOLO 跑通；正式方案为 RKNN，未转换', '流水线校验'),
    ('hr_docking AprilTag 定位', 'skeleton', '门控逻辑完整；Tag 实物、外参与 opennav_docking 均未到位', '11 条单元测试'),
    ('hr_depth_obstacle 深度障碍', 'skeleton', '门控与地面滤除完整；阈值待 Gemini 2 实测冻结', '11 条单元测试'),
    ('hr_arm_controller 抓取状态机', 'skeleton', '安全互锁完整；IK 与舵机驱动未实现', '12 条单元测试'),
    ('hr_voice_command 语音意图', 'skeleton', '白名单映射与拒绝策略完整；麦克风与 ASR 未选型', '12 条单元测试'),
    ('Nav2 导航栈', 'config', '参数骨架就位，缺已验收地图，未实机跑通', '—'),
    ('Collision Monitor 停止区', 'blocked', '停止区多边形仍为空 —— 待实测制动距离后才能冻结', '—'),
    ('Orbbec Gemini 2 接入', 'blocked', '方案已改为 Gemini 2，实物未接入；当前为 RTSP 调试取流', '—'),
    ('6轴机械臂 + 末端 D435i', 'blocked', '机械臂、舵机控制器、D435i 三者均未到位', '—'),
]


def main():
    row_h = 38
    top = 150
    H = top + len(ROWS) * row_h + 112
    out = header(W, H, '模块成熟度 · 实测与未实测分开记',
                 '「能跑」不是验收结论。下表把实机验收过的能力、只有单元测试的代码'
                 '和还在等硬件的部分分开陈述')

    # legend
    x = 32
    for key in ('measured', 'tested', 'skeleton', 'config', 'blocked'):
        label, fg, bg = LEVELS[key]
        w = 11 + len(label) * 12
        out.append(box(x, 86, w, 26, bg, fg, radius=13, width=1.3))
        out += wrap_text(x + w / 2, 103, [label], 11.5, fg, weight='700')
        x += w + 12

    # header row
    out.append(box(32, 124, W - 64, 24, PANEL, '#d0d7de', radius=6, width=1))
    for cx, label, anchor in ((48, '模块', 'start'), (430, '状态', 'start'),
                              (556, '当前到哪一步 / 卡在哪', 'start'),
                              (W - 48, '自动化验证', 'end')):
        out += wrap_text(cx, 140, [label], 11, MUTED, weight='700', anchor=anchor)

    for i, (name, level, note, tests) in enumerate(ROWS):
        y = top + i * row_h
        label, fg, bg = LEVELS[level]
        if i % 2 == 0:
            out.append(box(32, y, W - 64, row_h, '#fbfcfd', '#fbfcfd', radius=4, width=0))
        out += wrap_text(48, y + 24, [name], 12, INK, weight='600', anchor='start')
        pill_w = 11 + len(label) * 12
        out.append(box(430, y + 8, pill_w, 22, bg, fg, radius=11, width=1.2))
        out += wrap_text(430 + pill_w / 2, y + 23, [label], 10.5, fg, weight='700')
        out += wrap_text(556, y + 24, [note], 11, MUTED, anchor='start')
        fam = None if tests == '—' else MONO
        out += wrap_text(W - 48, y + 24, [tests], 10.5,
                         MUTED if tests == '—' else '#1a7f37', anchor='end', family=fam)
        out.append(f'<line x1="32" y1="{y + row_h}" x2="{W - 32}" y2="{y + row_h}" '
                   f'stroke="#e7ebef" stroke-width="1"/>')

    fy = top + len(ROWS) * row_h + 18
    out.append(box(32, fy, W - 64, 72, '#fff8e5', '#d4a72c', radius=8, width=1.2))
    out += wrap_text(48, fy + 22, ['这张表为什么这么写'], 11.5, INK, weight='700', anchor='start')
    for i, line in enumerate([
        '项目规范里有一条硬约束：验收标准必须可判定，证据必须落盘。'
        '「能跑」「实测正常」不算数，ros2 topic hz 的数字、colcon test-result 的输出、bag 文件才算。',
        '所以上面没有进度百分比，只有「这一条有没有可复现的证据」。'
        '缺件阻塞的行不会因为代码写完了就变绿 —— 它要等硬件、等标定、等实测数值。',
    ]):
        out += wrap_text(48, fy + 44 + i * 17, [line], 10.8, MUTED, anchor='start')

    out.append('</svg>')
    dest = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'images' / 'module-status.svg'
    dest.write_text('\n'.join(out), encoding='utf-8')
    print('wrote', dest)


if __name__ == '__main__':
    main()
