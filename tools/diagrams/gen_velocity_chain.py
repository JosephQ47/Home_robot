"""docs/images/velocity-chain.svg — the single path every automatic velocity takes.

This is the diagram the whole project hangs on. Two planners can propose a
velocity; exactly one node decides which proposal survives; one more node can
veto it outright; and a microcontroller that trusts none of them has the last
word. Each gate is annotated with what makes it fail closed.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from palette import (INK, LAYERS, MONO, MUTED, NEW, PANEL, SAFETY, arrow_defs,  # noqa: E402
                     box, header, wrap_text)

W, H = 1240, 560


def stage(x, y, w, h, title, sub, colour, fill, badge=None, emphasis=False):
    parts = [box(x, y, w, h, fill, colour, radius=10, width=2.6 if emphasis else 1.8)]
    parts += wrap_text(x + w / 2, y + 30, [title], 14, colour, weight='700', family=MONO)
    for i, line in enumerate(sub):
        parts += wrap_text(x + w / 2, y + 52 + i * 16, [line], 11.2, MUTED)
    if badge:
        parts.append(f'<rect x="{x + w - 36}" y="{y + 8}" width="30" height="16" rx="8" fill="{NEW}"/>')
        parts += wrap_text(x + w - 21, y + 20, [badge], 10, '#ffffff', weight='700')
    return parts


def gate(x, y, text, colour):
    """A small note explaining what makes this hop fail closed."""
    parts = [box(x, y, 250, 56, PANEL, '#d0d7de', radius=7, width=1)]
    for i, line in enumerate(text):
        parts += wrap_text(x + 125, y + 22 + i * 15, [line], 10.5, MUTED, anchor='middle')
    return parts


def main():
    blue, red = LAYERS['L4']['stroke'], SAFETY['stroke']
    teal, orange = LAYERS['L3']['stroke'], LAYERS['L2']['stroke']
    out = header(W, H, '自动速度安全链 · 一条路，四道闸',
                 '两个规划器可以「提议」速度，但只有一个节点决定谁的提议生效，'
                 '再由一个节点行使一票否决，最后由不信任任何上位机的 MCU 执行')
    defs, mk = arrow_defs([blue, red, teal, orange, MUTED])
    out = out[:1] + defs + out[1:]

    y0 = 112
    out += stage(32, y0, 230, 92, 'Nav2', ['导航 · 巡检 · 跟随', '→ /cmd_vel_nav'],
                 blue, '#ffffff')
    out += stage(32, y0 + 112, 230, 92, 'OpenNav Docking',
                 ['AprilTag 低速精对接', '→ /cmd_vel_dock'], blue, '#ffffff')

    out += stage(330, y0 + 34, 250, 148, 'hr_motion_mux',
                 ['按 MotionPhase 互斥选择', '切换先归零 300 ms',
                  '源过期即归零', '', '唯一输出 /cmd_vel_auto'],
                 blue, '#e3eefc', badge='NEW', emphasis=True)

    out += stage(648, y0 + 34, 250, 148, 'Collision Monitor',
                 ['基于最新 /scan 的停止区', '障碍进入 → 请求零速',
                  '', '唯一输出 /cmd_vel'],
                 red, SAFETY['fill'], emphasis=True)

    out += stage(966, y0 + 34, 242, 148, 'STM32F407',
                 ['命令超时 150 ms 归零', 'SBUS 接管优先于自动',
                  '限速 / 斜坡 / 限流', '', '物理执行的唯一权威'],
                 orange, '#fdeddc', emphasis=True)

    # flows
    out.append(f'<path d="M 262 {y0 + 46} H 300 V {y0 + 96} H 330" stroke="{blue}" '
               f'stroke-width="3" fill="none" marker-end="url(#{mk[blue]})"/>')
    out.append(f'<path d="M 262 {y0 + 158} H 300 V {y0 + 112} H 330" stroke="{blue}" '
               f'stroke-width="3" fill="none" marker-end="url(#{mk[blue]})"/>')
    out.append(f'<path d="M 580 {y0 + 108} H 648" stroke="{red}" stroke-width="3.4" '
               f'fill="none" marker-end="url(#{mk[red]})"/>')
    out.append(f'<path d="M 898 {y0 + 108} H 966" stroke="{red}" stroke-width="3.4" '
               f'fill="none" marker-end="url(#{mk[red]})"/>')
    out += wrap_text(614, y0 + 88, ['/cmd_vel_auto'], 11, SAFETY['text'],
                     weight='700', family=MONO)
    out += wrap_text(932, y0 + 88, ['/cmd_vel'], 11, SAFETY['text'], weight='700', family=MONO)
    out += wrap_text(932, y0 + 142, ['经 hr_bridge'], 10, MUTED, family=MONO)

    # what would break each gate
    gy = 396
    out += gate(32, gy, ['两个规划器都可以发速度，', '但都不能直接发 /cmd_vel'], MUTED)
    out += gate(330, gy, ['任务管理器停发阶段授权，', '这里 1 秒内归零'], MUTED)
    out += gate(648, gy, ['/scan 过期或本节点异常退出，', '自动任务在冻结时限内取消'], MUTED)
    out += gate(966, gy, ['上位机整体失联，', '150 ms 后底盘自行停车'], MUTED)
    for x, top in ((157, y0 + 204), (455, y0 + 182), (773, y0 + 182), (1091, y0 + 182)):
        out.append(f'<path d="M {x} {top} V {gy}" stroke="{MUTED}" stroke-width="1.4" '
                   f'fill="none" stroke-dasharray="4 3" marker-end="url(#{mk[MUTED]})"/>')

    out.append(box(32, 484, W - 64, 44, '#fff8e5', '#d4a72c', radius=8, width=1.2))
    out += wrap_text(48, 502, ['每一道闸都是「fail closed」'], 11.5, INK,
                     weight='700', anchor='start')
    out += wrap_text(48, 519,
                     ['坏掉的结果永远是停车，不是继续按最后一个命令跑。'
                      '回充速度同样走这条链——为了对接成功而关小停止区，属于禁止项，'
                      '只能回去改充电桩机械设计。'],
                     11, MUTED, anchor='start')
    out.append('</svg>')
    dest = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'images' / 'velocity-chain.svg'
    dest.write_text('\n'.join(out), encoding='utf-8')
    print('wrote', dest)


if __name__ == '__main__':
    main()
