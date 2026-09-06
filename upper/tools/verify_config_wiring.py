#!/usr/bin/env python3
"""审计 config/*.yaml 是否真的接进了 ROS 节点。

为什么需要这个
--------------
ROS 2 的参数 yaml 有两种静默失效，都不报任何错：

  1. **文件根本没被加载**：launch 里没有把它放进 `parameters=[...]`，
     节点也没有按路径读它。文件看着权威，改它等于改了个记事本。
  2. **顶层键与节点名不符**：文件加载了，但 `hr_local_motion:` 对上的节点
     实际叫 `nav2_local_controller_adapter`，整份参数被忽略。

两种都属于「接口名写错不报错，只是永远不生效」那一类。2026-09-07 实测：本工作
空间 15 个 config yaml 里，只有 2 个真正接线，1 个加载了但键名不符，其余 12 个
是死配置——包括刚写进去的毫米波标定 range_scale_m，写了完全不生效。

用法
----
  python3 upper/tools/verify_config_wiring.py            # 审计并打印
  python3 upper/tools/verify_config_wiring.py --quiet    # 只输出结论

退出码：0 = 没有键名不符；1 = 存在键名不符（确定性缺陷）。
「未被加载」只列出、不判失败——其中一部分是为将来预留的占位（如 locations.yaml
在地图验收前必然为空），该不该接线要人来裁决，不该由脚本替人决定。
"""
import argparse
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'src'


def node_names(launch_text):
    """launch 文件里声明的所有节点名。"""
    return set(re.findall(r"name=['\"]([\w/]+)['\"]", launch_text))


def top_key(yaml_path):
    for line in yaml_path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        return stripped.rstrip(':').strip()
    return ''


def audit():
    yamls = sorted(SRC.glob('*/config/*.yaml'))
    launches = sorted(SRC.glob('*/launch/*.launch.py'))
    sources = [p for p in SRC.glob('*/*/*.py') if 'launch' not in p.parts]
    launch_text = {p: p.read_text(encoding='utf-8') for p in launches}
    source_blob = '\n'.join(p.read_text(encoding='utf-8') for p in sources)

    wired, mismatched, orphan = [], [], []
    for y in yamls:
        name = y.name
        holders = [p for p, t in launch_text.items() if name in t]
        if not holders:
            if name in source_blob:
                wired.append((y, '(节点源码按路径读取)', ''))
            else:
                orphan.append(y)
            continue
        key = top_key(y)
        for lf in holders:
            names = node_names(launch_text[lf])
            if key.startswith('/**') or key in names:
                wired.append((y, lf.name, key))
            else:
                mismatched.append((y, lf.name, key, sorted(names)))
    return wired, mismatched, orphan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()
    wired, mismatched, orphan = audit()

    if not args.quiet:
        print('── 已接线 ──')
        for y, where, key in wired:
            print(f'  ✅ {y.parent.parent.name}/{y.name:<26} ← {where}  键={key}')
        print()
        print('── 键名与节点名不符（参数被静默忽略）──')
        for y, lf, key, names in mismatched or []:
            print(f'  ❌ {y.parent.parent.name}/{y.name}')
            print(f'       顶层键 {key!r}，但 {lf} 里的节点名是 {names}')
        if not mismatched:
            print('  （无）')
        print()
        print('── 未被任何 launch 或节点引用（死配置，改了不生效）──')
        for y in orphan:
            print(f'  ⚠️  {y.parent.parent.name}/{y.name}')
        if not orphan:
            print('  （无）')
        print()

    print(f'合计 {len(wired) + len(mismatched) + len(orphan)} 个 config yaml：'
          f'已接线 {len(wired)} · 键名不符 {len(mismatched)} · 死配置 {len(orphan)}')
    if mismatched:
        print('存在键名不符 —— 这些参数正在被静默忽略，必须修。')
        return 1
    print('没有键名不符。死配置只列出不判失败：其中部分是为将来预留的占位，'
          '该不该接线由人裁决。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
