"""docs/images/freertos-tasks.svg — the four STM32 tasks and what they refuse to share.

The point of the diagram is the isolation, not the boxes: tasks exchange only
latest-value snapshots behind sequence locks, so a task that blocks cannot stall
the control loop, and monitor_task can veto everything without asking permission.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from palette import (INK, LAYERS, MONO, MUTED, PANEL, SAFETY, arrow_defs, box,  # noqa: E402
                     header, wrap_text)

W, H = 1240, 700
L2 = LAYERS['L2']
L1 = LAYERS['L1']


def task(x, y, w, h, name, hz, rows, colour, fill):
    parts = [box(x, y, w, h, fill, colour, radius=10, width=2.2)]
    parts += wrap_text(x + w / 2, y + 28, [name], 14.5, colour, weight='700', family=MONO)
    parts.append(f'<rect x="{x + w - 78}" y="{y + 12}" width="66" height="19" rx="9.5" '
                 f'fill="{colour}" opacity="0.14"/>')
    parts += wrap_text(x + w - 45, y + 25.5, [hz], 10.5, colour, weight='700')
    for i, (label, value) in enumerate(rows):
        yy = y + 52 + i * 18
        parts += wrap_text(x + 16, yy, [label], 10.5, MUTED, anchor='start', weight='700')
        parts += wrap_text(x + w - 16, yy, [value], 10.5, INK, anchor='end')
    return parts


def main():
    out = header(W, H, '下位机 FreeRTOS · 四任务与隔离边界',
                 '任务之间只交换「最新值快照」，不排队、不互等；'
                 '任何一个任务卡住都不能拖垮 1 ms 控制节拍')
    colours = [L2['stroke'], SAFETY['stroke'], L1['stroke'], MUTED]
    defs, mk = arrow_defs(colours)
    out = out[:1] + defs + out[1:]

    out += task(32, 96, 372, 150, 'command_task', '100 Hz', [
        ('输入', 'CmdFrame · SBUS · SafetyPermit'),
        ('输出', 'CommandState_t 最新快照'),
        ('上位机超时', '150 ms → 目标归零'),
        ('SBUS 超时', '50 ms → 目标归零'),
        ('铁律', '旧 source_seq 不得恢复运动'),
    ], L2['stroke'], '#ffffff')

    out += task(436, 96, 372, 150, 'chassis_task', '1 kHz', [
        ('安全/PWM 节拍', '1 ms'),
        ('测速/PI 子周期', '10 ms'),
        ('速度 PI', 'Kp=0.40 · Ki=0.80 s⁻¹'),
        ('换向', '零 PWM → <10 rpm → 等 50 ms'),
        ('输出', '4×PWM/方向/使能 + WheelOdom'),
    ], L2['stroke'], '#ffffff')

    out += task(840, 96, 368, 150, 'imu_task', '1 kHz', [
        ('BMI088', 'SPI + DMA，1 kHz'),
        ('IST8310', 'I2C，100 Hz'),
        ('姿态', 'Mahony，四元数归一化'),
        ('磁场异常', '降级 6 轴，置 mag_degraded'),
        ('输出', 'ImuSample_t（不出欧拉航向）'),
    ], L2['stroke'], '#ffffff')

    out += task(436, 286, 372, 168, 'monitor_task', '1 kHz', [
        ('输入', '急停 · 故障 · 心跳 · 电池快照'),
        ('输出', 'SafetyPermit · BatteryLevel'),
        ('', 'FaultCode · IWDG 喂狗许可'),
        ('电量分级', 'LOW / DOCK_RESERVE / CRITICAL'),
        ('', 'INVALID / CHARGING'),
        ('过流切断', '8 A / 5 ms'),
        ('堵转判据', '6 A + <10 rpm + PWM≥40% + 300 ms'),
    ], SAFETY['stroke'], SAFETY['fill'])

    red, orange, grey = SAFETY['stroke'], L2['stroke'], L1['stroke']
    out.append(f'<path d="M 404 171 H 436" stroke="{orange}" stroke-width="2.6" fill="none" '
               f'marker-end="url(#{mk[orange]})"/>')
    out.append(f'<path d="M 808 171 H 840" stroke="{grey}" stroke-width="1.8" fill="none" '
               f'stroke-dasharray="5 4" marker-end="url(#{mk[grey]})"/>')

    # the veto: monitor reaches both movement-producing tasks, and neither can refuse
    out.append(f'<path d="M 520 286 V 246" stroke="{red}" stroke-width="2.8" fill="none" '
               f'marker-end="url(#{mk[red]})"/>')
    out.append(f'<path d="M 470 286 V 266 H 218 V 246" stroke="{red}" stroke-width="2.8" '
               f'fill="none" marker-end="url(#{mk[red]})"/>')
    out.append(f'<path d="M 780 286 V 266 H 1024 V 246" stroke="{grey}" stroke-width="1.8" '
               f'fill="none" stroke-dasharray="5 4" marker-end="url(#{mk[grey]})"/>')
    out += wrap_text(620, 278, ['SafetyPermit（否决权，被监控方无权拒绝）'], 10.5,
                     SAFETY['text'], weight='700')

    # IPC rules
    out.append(box(32, 286, 372, 168, PANEL, '#d0d7de', radius=10, width=1.2))
    out += wrap_text(48, 310, ['任务间数据交换机制'], 12, INK, weight='700', anchor='start')
    rules = [
        '· 只传「最新值」，不排队：旧命令永远不补执行',
        '· 快照用序列锁：读前后 lock_seq 相等且为偶数才可用',
        '· 连续 3 次读取失败 → 按数据不可用处理',
        '· 每条数据自带时间戳与 valid 标志',
        '· 新鲜度判据：等于阈值可用，超阈值 1 ms 即失效',
        '· 32 位单调时钟回绕必须判定正确',
        '· ISR 只做采集、清标志和通知，不做运算',
    ]
    for i, r in enumerate(rules):
        out += wrap_text(48, 334 + i * 17, [r], 10.5, MUTED, anchor='start')

    out.append(box(840, 286, 368, 168, PANEL, '#d0d7de', radius=10, width=1.2))
    out += wrap_text(856, 310, ['看门狗：软件存活门，不是定时器'], 12, INK,
                     weight='700', anchor='start')
    wd = [
        'monitor_task 只有在确认另外三个任务',
        '都在规定期限内「报到」之后，才去喂 IWDG。',
        '',
        '所以任何一个被监控任务挂死，IWDG 会超时复位，',
        '而不是让机器人带着一个死任务继续跑。',
        '',
        'monitor_task 自己挂死同样触发复位，',
        '复位原因记入 reset_cause 并随状态帧上报。',
    ]
    for i, r in enumerate(wd):
        out += wrap_text(856, 334 + i * 17, [r], 10.5, MUTED, anchor='start')

    # hard boundary
    out.append(box(32, 486, W - 64, 78, '#fff8e5', '#d4a72c', radius=8, width=1.2))
    out += wrap_text(48, 510, ['为什么这四个任务不能再拆细'], 11.5, INK,
                     weight='700', anchor='start')
    for i, line in enumerate([
        '拆得越细，跨任务共享的状态越多，需要保护的临界区也越多——'
        '而每一个临界区都是一次潜在的优先级反转和一次新的时序不确定性。',
        '四任务的边界按「谁拥有哪份数据」划分：命令的所有者是 command_task，'
        '轮子的所有者是 chassis_task，姿态的所有者是 imu_task，安全裁决的所有者是 monitor_task。',
        '没有第二个任务可以写别人的数据，所以也不需要互斥锁来争抢它。',
    ]):
        out += wrap_text(48, 530 + i * 16, [line], 10.5, MUTED, anchor='start')

    out.append(box(32, 584, W - 64, 84, PANEL, '#d0d7de', radius=8, width=1))
    out += wrap_text(48, 608, ['验收怎么做（技术方案 §10.2）'], 11.5, INK,
                     weight='700', anchor='start')
    for i, line in enumerate([
        '· 分别挂起 command / chassis / imu 三个被监控任务，验证安全输出与 IWDG 复位；',
        '· 单独阻塞 monitor_task、制造关键 ISR 停止和调度死锁，验证同样会复位；',
        '· 记录四任务平均/最大执行时间、抖动和 deadline miss，连续满负载不得越限。',
    ]):
        out += wrap_text(48, 628 + i * 16, [line], 10.5, MUTED, anchor='start')

    out.append('</svg>')
    dest = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'images' / 'freertos-tasks.svg'
    dest.write_text('\n'.join(out), encoding='utf-8')
    print('wrote', dest)


if __name__ == '__main__':
    main()
