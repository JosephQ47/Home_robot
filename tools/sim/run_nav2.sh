#!/usr/bin/env bash
# Bring up the real Nav2 stack over the planar simulator and the saved map, then
# drive one navigation goal through the whole safety chain.
#
# Activation is left to nav2_lifecycle_manager rather than a loop of
# `ros2 lifecycle set`: each of those spins up its own CLI node and has to
# discover the target service, which on a busy graph fails often enough that the
# stack half-activates and the failure looks like a configuration problem.
set -e
SP="$1"
source /opt/ros/humble/setup.bash
source /home/luckfox/d2lros2/Home_robot/upper/install/setup.bash
cd /home/luckfox/d2lros2/Home_robot/upper
I=install
MAP=/home/luckfox/d2lros2/Home_robot/upper/src/hr_localization/maps/home1.yaml

ros2 daemon stop > /dev/null 2>&1 || true
sleep 2

# The simulator already publishes odom->base_link, so no EKF here; AMCL supplies
# map->odom and nothing else competes for either transform.
ros2 run hr_simulation planar_sim --ros-args \
  -p floorplan_file:=$PWD/$I/hr_simulation/share/hr_simulation/config/home_floorplan.yaml \
  > "$SP/n_sim.log" 2>&1 & PIDS="$!"
sleep 4

ros2 run nav2_map_server map_server --ros-args -p yaml_filename:="$MAP" \
  > "$SP/n_map.log" 2>&1 & PIDS="$PIDS $!"
ros2 run nav2_amcl amcl --ros-args \
  --params-file $PWD/$I/hr_localization/share/hr_localization/config/amcl.yaml \
  > "$SP/n_amcl.log" 2>&1 & PIDS="$PIDS $!"
ros2 run nav2_lifecycle_manager lifecycle_manager --ros-args \
  -r __node:=lifecycle_manager_localization \
  -p autostart:=true -p bond_timeout:=12.0 \
  -p "node_names:=['map_server','amcl']" > "$SP/n_lmloc.log" 2>&1 & PIDS="$PIDS $!"

sleep 12
echo "--- seeding the initial pose so AMCL can publish map->odom ---"
# The costmaps block on map->base_link and AMCL cannot provide map->odom until it
# is told roughly where the robot is. The map frame's origin is the pose the
# robot started mapping from, so that is (0, 0, 0).
for i in 1 2 3; do
  ros2 topic pub --once /initialpose geometry_msgs/PoseWithCovarianceStamped \
    "{header: {frame_id: map}, pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}, covariance: [0.25,0,0,0,0,0, 0,0.25,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0.07]}}" \
    > /dev/null 2>&1 || true
  sleep 2
done

# The project's own launch file, so the bench exercises the shipped wiring.
ros2 launch hr_navigation navigation.launch.py enable_real_navigation:=true \
  > "$SP/n_nav2.log" 2>&1 & PIDS="$PIDS $!"

sleep 30
echo "--- lifecycle states ---"
for n in map_server amcl collision_monitor controller_server planner_server behavior_server bt_navigator waypoint_follower; do
  printf "%-20s %s\n" "$n" "$(timeout 10 ros2 lifecycle get /$n 2>&1 | head -1)"
done
echo ""

python3 "$SP/verify_nav2.py"

for p in $PIDS; do pkill -9 -P "$p" 2>/dev/null; kill -9 "$p" 2>/dev/null; done
wait 2>/dev/null
sleep 1
ros2 daemon stop > /dev/null 2>&1 || true
exit 0
