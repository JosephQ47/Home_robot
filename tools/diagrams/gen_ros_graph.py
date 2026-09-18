"""docs/images/ros-graph.svg — the real ROS computation graph.

Not drawn by hand. tools/diagrams/capture_ros_graph.sh brings the system up,
reads the live graph through rclpy's node/topic introspection, and writes
graph.json; this script lays that out. If a node stops publishing something,
the picture changes the next time it is regenerated.

The point it makes is the one the whole project is built around: /cmd_vel_auto
has exactly one publisher and /cmd_vel has exactly one publisher.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from palette import INK, LAYERS, MONO, MUTED, NEW, PANEL, SAFETY, arrow_defs, box, header, wrap_text  # noqa: E402

W = 1240

# Where each node sits, and which layer colour it takes. Topics are placed
# between the nodes that use them.
COLUMNS = [
    ('业务任务', 'L5', ['/hr_voice_capture', '/hr_voice_command', '/hr_task_manager']),
    ('感知与规划', 'L4', ['/hr_depth_obstacle', '/hr_dock_pose_adapter', '/hr_motion_mux']),
    ('安全否决', 'L4', ['/collision_monitor']),
    ('机械臂', 'L2', ['/hr_arm_controller', '/hr_arm_driver']),
]

# The chain we highlight, in order.
CHAIN = ['/cmd_vel_nav', '/cmd_vel_dock', '/cmd_vel_auto', '/cmd_vel']


def load(path):
    data = json.loads(pathlib.Path(path).read_text())
    nodes = [n for n in data['nodes'] if not n.startswith('/_ros2cli')]
    edges = [e for e in data['edges']
             if not e['from'].startswith('/_ros2cli') and not e['to'].startswith('/_ros2cli')]
    return nodes, edges


def main(graph_json):
    nodes, edges = load(graph_json)
    pubs = {}
    for e in edges:
        if e['dir'] == 'pub':
            pubs.setdefault(e['to'], []).append(e['from'])

    rows = []
    for topic in CHAIN:
        rows.append((topic, pubs.get(topic, [])))

    node_rows = sorted(n for n in nodes if 'transform_listener' not in n)
    H = 250 + len(node_rows) * 30 + len(rows) * 34

    out = header(W, H, '真实 ROS 计算图 · 从运行中的系统抓取',
                 '不是手画的。把系统跑起来，用 rclpy 读活的节点与话题拓扑，'
                 '再渲染成这张图 —— 谁发布了什么，图上就是什么')
    defs, mk = arrow_defs([LAYERS['L4']['stroke'], SAFETY['stroke'], MUTED])
    out = out[:1] + defs + out[1:]

    y = 104
    out.append(box(32, y, W - 64, 30 + len(node_rows) * 30, PANEL, '#d0d7de', radius=10, width=1))
    out += wrap_text(48, y + 21, [f'ros2 node list — {len(node_rows)} 个节点在运行'], 12,
                     INK, weight='700', anchor='start', family=MONO)
    for i, n in enumerate(node_rows):
        yy = y + 42 + i * 30
        out.append(box(48, yy - 15, 300, 24, '#ffffff', LAYERS['L4']['stroke'], radius=6, width=1.2))
        out += wrap_text(58, yy + 2, [n], 11.5, LAYERS['L4']['text'], anchor='start', family=MONO)
        published = [e['to'] for e in edges if e['dir'] == 'pub' and e['from'] == n]
        subscribed = [e['from'] for e in edges if e['dir'] == 'sub' and e['to'] == n]
        out += wrap_text(368, yy + 2, [f'发布 {len(published)} · 订阅 {len(subscribed)}'],
                         11, MUTED, anchor='start')
        interesting = [t for t in published if t in CHAIN or t.startswith('/arm/')
                       or t.startswith('/task/') or t.startswith('/voice/')
                       or t.startswith('/obstacle/') or t == '/detected_dock_pose']
        if interesting:
            out += wrap_text(500, yy + 2, ['→ ' + '  '.join(sorted(interesting)[:4])],
                             10.5, MUTED, anchor='start', family=MONO)

    y = y + 46 + len(node_rows) * 30
    out.append(box(32, y, W - 64, 34 + len(rows) * 34, '#ffffff', SAFETY['stroke'],
                   radius=10, width=2))
    out += wrap_text(48, y + 23,
                     ['速度链上每个话题的发布者 —— /cmd_vel_auto 与 /cmd_vel 必须各恰好一个'],
                     12, SAFETY['text'], weight='700', anchor='start')
    for i, (topic, publishers) in enumerate(rows):
        yy = y + 48 + i * 34
        out += wrap_text(58, yy + 4, [topic], 12, INK, anchor='start', family=MONO, weight='700')
        count = len(publishers)
        # The invariant is "at most one", and exactly one on the two topics that
        # actually reach the chassis. More than one is the failure; zero on a
        # candidate topic just means that planner was not part of this capture.
        critical = topic in ('/cmd_vel_auto', '/cmd_vel')
        if count > 1 or (critical and count != 1):
            badge = SAFETY['stroke']
        elif count == 1:
            badge = NEW
        else:
            badge = MUTED
        out.append(box(300, yy - 10, 118, 22, '#ffffff', badge, radius=11, width=1.6))
        out += wrap_text(359, yy + 4, [f'publisher × {count}'], 11, badge, weight='700')
        names = ', '.join(p for p in publishers) or '候选源，本次抓取未启动'
        out += wrap_text(440, yy + 4, [names], 11.5, MUTED, anchor='start', family=MONO)

    y = y + 44 + len(rows) * 34
    out.append(box(32, y, W - 64, 46, '#fff8e5', '#d4a72c', radius=8, width=1.2))
    out += wrap_text(48, y + 20, ['为什么这张图值得单独放出来'], 11.5, INK,
                     weight='700', anchor='start')
    out += wrap_text(48, y + 37,
                     ['「只有一个节点能发最终速度」写在文档里是一句主张，'
                      '写在这张从运行系统抓取的拓扑里才是一个事实。'],
                     11, MUTED, anchor='start')
    out.append('</svg>')

    dest = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'images' / 'ros-graph.svg'
    dest.write_text('\n'.join(out), encoding='utf-8')
    print('wrote', dest)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'graph.json')
