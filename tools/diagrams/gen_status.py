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
    'onrobot':  ('实机运行', '#1a7f37', '#dafbe1'),
    'verified': ('链路验证', '#1a73e8', '#ddf4ff'),
    'covered':  ('自动化覆盖', '#8250df', '#f3e8ff'),
    'wired':    ('已接线', '#57606a', '#eaeef2'),
}

# (module, level, note, tests)
ROWS = [
    ('底盘四轮闭环与安全链', 'onrobot', '真实制动、急停、断链停车、过流与堵转保护', '实机'),
    ('上下位机协议 hr_bridge', 'onrobot', 'CRC16 + 序号 + 心跳；断链重连与命令超时归零', '回环·丢帧·乱序'),
    ('自动速度链 mux + 停止区', 'verified', '两话题各恰好一个发布者；阶段互斥与激光否决全链跑通', '12 条 + 7 项'),
    ('语音→任务→机械臂 全链', 'verified', '一句话走完派发、互锁、抓取、放置、回零', '18 条 + 6 项'),
    ('抓取状态机与六轴 IK', 'verified', '完整抓取序列跑通；FK/IK 往返误差 1e-16', '35 条 + 6 项'),
    ('末端 D435i 视觉与手眼', 'verified', '反投影落在针孔模型解析值上；标定失效即拒绝启动', '28 条 + 8 项'),
    ('AprilTag 回充位姿', 'verified', 'ID/汉明/裕度/跳变/TF 新鲜度五重门控', '11 条 + 8 项'),
    ('舵机控制器链路', 'verified', '长度前缀 + CRC16 帧协议，半帧/粘包/乱序可重同步', '14 条单元测试'),
    ('唤醒词与 ASR 适配', 'verified', '一次唤醒一条命令；置信度解析失败取零不取一', '12 条 + 6 项'),
    ('任务编排与阶段授权', 'verified', '授权持续续发，停发即归零；四类来源互斥仲裁', '生命周期 + 18 条'),
    ('网页控制台', 'verified', '地图/区域/目标/模式下发，任务队列实时回写', '后端单元测试'),
    ('深度障碍门控', 'covered', '地面滤除、有效率门控、空洞按未知处理', '11 条单元测试'),
    ('语音意图白名单', 'covered', '十一条命令的映射与全部拒绝路径', '12 条单元测试'),
    ('视觉识别', 'covered', 'YOLO 二维检测与事件门控', '流水线校验'),
    ('Nav2 / AMCL 节点组', 'wired', '五节点 + lifecycle 编排，与建图模式互斥', '拓扑检查'),
    ('SLAM 建图', 'wired', 'slam_toolbox 异步建图入口', '拓扑检查'),
]



def main():
    row_h = 38
    top = 150
    H = top + len(ROWS) * row_h + 112
    out = header(W, H, '能力与验证方式',
                 '每一行都写清楚这件事是怎么被证明的 —— 实机跑过、整条链路跑过、'
                 '还是自动化测试覆盖')

    # legend
    x = 32
    for key in ('onrobot', 'verified', 'covered', 'wired'):
        label, fg, bg = LEVELS[key]
        w = 11 + len(label) * 12
        out.append(box(x, 86, w, 26, bg, fg, radius=13, width=1.3))
        out += wrap_text(x + w / 2, 103, [label], 11.5, fg, weight='700')
        x += w + 12

    # header row
    out.append(box(32, 124, W - 64, 24, PANEL, '#d0d7de', radius=6, width=1))
    for cx, label, anchor in ((48, '模块', 'start'), (430, '状态', 'start'),
                              (556, '做到了什么', 'start'),
                              (W - 48, '验证方式', 'end')):
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
        '所以这里没有进度百分比，只有「这一条是怎么被证明的」。'
        '全部证据在 docs/acceptance/，每一项都能照着命令重跑一遍。',
    ]):
        out += wrap_text(48, fy + 44 + i * 17, [line], 10.8, MUTED, anchor='start')

    out.append('</svg>')
    dest = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'images' / 'module-status.svg'
    dest.write_text('\n'.join(out), encoding='utf-8')
    print('wrote', dest)


if __name__ == '__main__':
    main()
