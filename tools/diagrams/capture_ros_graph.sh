#!/usr/bin/env bash
set -e
SP="$1"
source /opt/ros/humble/setup.bash
source /home/luckfox/d2lros2/Home_robot/upper/install/setup.bash
cd /home/luckfox/d2lros2/Home_robot/upper
I=install

# The ros2 daemon caches discovery and will keep reporting nodes that have
# already exited, which shows up as duplicates in the captured graph.
ros2 daemon stop > /dev/null 2>&1 || true
sleep 2

ros2 run hr_motion_mux motion_mux --ros-args \
  --params-file $I/hr_motion_mux/share/hr_motion_mux/config/motion_mux.yaml > "$SP/g1.log" 2>&1 & P1=$!
ros2 run nav2_collision_monitor collision_monitor --ros-args \
  --params-file $I/hr_navigation/share/hr_navigation/config/collision_monitor.yaml > "$SP/g2.log" 2>&1 & P2=$!
ros2 run hr_arm_driver arm_driver --ros-args \
  --params-file $I/hr_arm_driver/share/hr_arm_driver/config/arm_driver.yaml > "$SP/g3.log" 2>&1 & P3=$!
ros2 run hr_arm_controller arm_controller --ros-args \
  --params-file $I/hr_arm_controller/share/hr_arm_controller/config/arm_controller.yaml > "$SP/g4.log" 2>&1 & P4=$!
ros2 run hr_task_manager task_manager --ros-args \
  -p mock_navigation_enabled:=true -p grasp_work_pose:=工作位 \
  -p "work_pose_xyyaw:=[2.6, 3.1, 1.57]" > "$SP/g5.log" 2>&1 & P5=$!
ros2 run hr_voice_capture voice_capture --ros-args \
  -p asr_adapter:=text -p wake_word:=小家 > "$SP/g6.log" 2>&1 & P6=$!
ros2 run hr_voice_command voice_command --ros-args \
  -p "target_classes:=['杯子']" > "$SP/g7.log" 2>&1 & P7=$!
ros2 run hr_docking dock_pose_adapter --ros-args \
  --params-file $I/hr_docking/share/hr_docking/config/docks.yaml > "$SP/g8.log" 2>&1 & P8=$!
ros2 run hr_depth_obstacle depth_obstacle --ros-args \
  --params-file $I/hr_depth_obstacle/share/hr_depth_obstacle/config/depth_obstacle.yaml > "$SP/g9.log" 2>&1 & P9=$!
# The real producers of the two candidate velocities, so the chain shows its
# actual publishers rather than empty slots.
ros2 run hr_local_motion local_motion --ros-args \
  --params-file $I/hr_local_motion/share/hr_local_motion/config/local_motion.yaml \
  -p output_enabled:=true > "$SP/g10.log" 2>&1 & P10=$!
ros2 run opennav_docking opennav_docking --ros-args \
  --params-file "$SP/docking_bench.yaml" \
  -r cmd_vel:=/cmd_vel_dock > "$SP/g11.log" 2>&1 & P11=$!

sleep 10
ros2 lifecycle set /collision_monitor configure > /dev/null 2>&1 || true
sleep 1
ros2 lifecycle set /collision_monitor activate > /dev/null 2>&1 || true
ros2 lifecycle set /docking_server configure > /dev/null 2>&1 || true
sleep 1
ros2 lifecycle set /docking_server activate > /dev/null 2>&1 || true
sleep 4

echo "===== ros2 node list ====="      >  "$SP/graph_raw.txt"
ros2 node list                          >> "$SP/graph_raw.txt"
echo ""                                 >> "$SP/graph_raw.txt"
echo "===== ros2 topic list -t ====="  >> "$SP/graph_raw.txt"
ros2 topic list -t                      >> "$SP/graph_raw.txt"
echo ""                                 >> "$SP/graph_raw.txt"
echo "===== ros2 action list ====="    >> "$SP/graph_raw.txt"
ros2 action list                        >> "$SP/graph_raw.txt"
echo ""                                 >> "$SP/graph_raw.txt"
for t in /cmd_vel_nav /cmd_vel_dock /cmd_vel_auto /cmd_vel /task/motion_phase; do
  echo "===== ros2 topic info $t ====="  >> "$SP/graph_raw.txt"
  ros2 topic info "$t" --verbose 2>/dev/null | grep -E "Type|count|Node name" >> "$SP/graph_raw.txt"
  echo "" >> "$SP/graph_raw.txt"
done

# machine-readable edges for the diagram
python3 "$SP/dump_ros_graph.py" > "$SP/graph.json" 2>"$SP/dump.err" || cat "$SP/dump.err"

for p in $P1 $P2 $P3 $P4 $P5 $P6 $P7 $P8 $P9 $P10 $P11; do
  pkill -9 -P "$p" 2>/dev/null; kill -9 "$p" 2>/dev/null
done
wait 2>/dev/null
sleep 1
ros2 daemon stop > /dev/null 2>&1 || true
exit 0
