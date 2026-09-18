#!/usr/bin/env bash
set -e
SP="$1"
source /opt/ros/humble/setup.bash
source /home/luckfox/d2lros2/Home_robot/upper/install/setup.bash
cd /home/luckfox/d2lros2/Home_robot/upper
I=install
ros2 daemon stop > /dev/null 2>&1 || true
sleep 2

ros2 run hr_simulation planar_sim --ros-args \
  -p floorplan_file:=$PWD/$I/hr_simulation/share/hr_simulation/config/home_floorplan.yaml -p odom_noise:=0.002 -p scan_rate_hz:=15.0 \
  > "$SP/m_sim.log" 2>&1 & P1=$!
sleep 4
ros2 run slam_toolbox async_slam_toolbox_node --ros-args \
  --params-file "$SP/slam_bench.yaml" > "$SP/m_slam.log" 2>&1 & P2=$!
sleep 6

python3 "$SP/drive_tour.py" 1500
sleep 4

mkdir -p /home/luckfox/d2lros2/Home_robot/upper/src/hr_localization/maps
cd /home/luckfox/d2lros2/Home_robot/upper/src/hr_localization/maps
ros2 run nav2_map_server map_saver_cli -f home1 --ros-args -p save_map_timeout:=20.0 \
  > "$SP/m_save.log" 2>&1 || cat "$SP/m_save.log"
cd - > /dev/null

for p in $P1 $P2; do pkill -9 -P "$p" 2>/dev/null; kill -9 "$p" 2>/dev/null; done
wait 2>/dev/null
sleep 1
ros2 daemon stop > /dev/null 2>&1 || true
exit 0
