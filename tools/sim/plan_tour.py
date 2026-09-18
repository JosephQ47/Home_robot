"""Plan a collision-free mapping tour through the floor plan.

Hand-picked waypoints kept clipping furniture and wall corners, and a simulator
that now refuses to drive through walls turns each of those into a stall. So the
route is planned on an inflated occupancy grid instead: pick one goal per room,
then BFS between them through free cells.
"""
import heapq
import json
import math
import sys

sys.path.insert(0, '/home/luckfox/d2lros2/Home_robot/upper/src/hr_simulation')
import yaml
from hr_simulation.floorplan import blocked, build

RES = 0.05
RADIUS = 0.34          # robot radius plus tracking error, so the path is not wall-hugging


def main(plan_file):
    plan = yaml.safe_load(open(plan_file, encoding='utf-8'))['floorplan']
    segs = build(plan)
    o = plan['outer']
    nx = int((o['x_max'] - o['x_min']) / RES) + 1
    ny = int((o['y_max'] - o['y_min']) / RES) + 1

    def world(i, j):
        return o['x_min'] + i * RES, o['y_min'] + j * RES

    free = [[not blocked(*world(i, j), segs, RADIUS) for j in range(ny)] for i in range(nx)]

    def cell(x, y):
        return int(round((x - o['x_min']) / RES)), int(round((y - o['y_min']) / RES))

    def nearest_free(x, y):
        ci, cj = cell(x, y)
        best, bd = None, 1e9
        for i in range(nx):
            for j in range(ny):
                if not free[i][j]:
                    continue
                d = (i - ci) ** 2 + (j - cj) ** 2
                if d < bd:
                    best, bd = (i, j), d
        return best

    def astar(start, goal):
        openq = [(0, start)]
        came, cost = {start: None}, {start: 0}
        while openq:
            _, cur = heapq.heappop(openq)
            if cur == goal:
                break
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nb = (cur[0] + di, cur[1] + dj)
                if not (0 <= nb[0] < nx and 0 <= nb[1] < ny) or not free[nb[0]][nb[1]]:
                    continue
                step = math.hypot(di, dj)
                nc = cost[cur] + step
                if nb not in cost or nc < cost[nb]:
                    cost[nb] = nc
                    came[nb] = cur
                    h = math.hypot(nb[0] - goal[0], nb[1] - goal[1])
                    heapq.heappush(openq, (nc + h, nb))
        if goal not in came:
            return None
        path, cur = [], goal
        while cur is not None:
            path.append(cur)
            cur = came[cur]
        return list(reversed(path))

    # One representative goal per room, plus a couple of extra viewpoints so the
    # laser sees each room from more than one angle (loop closure needs that).
    stops = [(2.0, 5.2), (1.2, 6.0), (2.9, 6.6), (1.0, 4.4), (1.8, 3.6),
             (1.0, 2.6), (2.6, 2.4), (1.2, 2.2), (1.8, 3.6),
             (2.6, 1.0), (4.0, 0.9), (5.8, 2.2), (4.0, 2.6), (5.2, 3.0),
             (5.2, 4.4), (6.1, 4.6), (4.4, 4.6), (5.2, 5.6),
             (4.4, 6.0), (6.0, 6.2), (5.2, 5.6), (5.2, 3.6),
             (5.2, 2.0), (3.6, 1.4), (1.8, 2.8), (1.8, 3.6), (2.0, 5.2)]

    route, prev = [], nearest_free(*stops[0])
    route.append(world(*prev))
    for sx, sy in stops[1:]:
        goal = nearest_free(sx, sy)
        path = astar(prev, goal)
        if path is None:
            print(f'# unreachable: {sx},{sy}', file=sys.stderr)
            continue
        # Thin the grid path down to waypoints every ~0.35 m.
        for k in range(1, len(path)):
            wx, wy = world(*path[k])
            if math.hypot(wx - route[-1][0], wy - route[-1][1]) >= 0.15 or k == len(path) - 1:
                route.append((round(wx, 3), round(wy, 3)))
        prev = goal

    # Confirm the finished route never clips anything.
    bad = 0
    for i in range(len(route) - 1):
        (x1, y1), (x2, y2) = route[i], route[i + 1]
        steps = max(2, int(math.hypot(x2 - x1, y2 - y1) / 0.02))
        for k in range(steps + 1):
            t = k / steps
            if blocked(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, segs, 0.25):
                bad += 1
                break
    print(f'# waypoints={len(route)} blocked_legs={bad}', file=sys.stderr)
    print(json.dumps(route))


main(sys.argv[1])
