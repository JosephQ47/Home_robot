"""Read the live ROS graph and emit the publisher/subscriber edges as JSON."""
import json

import rclpy
from rclpy.node import Node

SKIP_NODES = {'/dump_graph', '/_ros2cli_daemon_0', '/rosout'}
SKIP_TOPICS = {'/rosout', '/parameter_events'}

rclpy.init()
n = Node('dump_graph')
import time
time.sleep(2.0)

nodes, edges = [], []
for name, ns in n.get_node_names_and_namespaces():
    full = (ns.rstrip('/') + '/' + name) if ns != '/' else '/' + name
    if full in SKIP_NODES or 'transform_listener' in full:
        continue
    nodes.append(full)
    for topic, types in n.get_publisher_names_and_types_by_node(name, ns):
        if topic in SKIP_TOPICS:
            continue
        edges.append({'from': full, 'to': topic, 'type': types[0], 'dir': 'pub'})
    for topic, types in n.get_subscriber_names_and_types_by_node(name, ns):
        if topic in SKIP_TOPICS:
            continue
        edges.append({'from': topic, 'to': full, 'type': types[0], 'dir': 'sub'})

print(json.dumps({'nodes': sorted(nodes), 'edges': edges}, ensure_ascii=False, indent=1))
n.destroy_node()
rclpy.shutdown()
