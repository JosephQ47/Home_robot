cmake_minimum_required(VERSION 3.8)
project(hr_interfaces)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RobotStatus.msg"
  "msg/FaultEvent.msg"
  "msg/TaskStatus.msg"
  "msg/FollowTarget.msg"
  "msg/PerceptionControl.msg"
  "msg/TrackerPolicy.msg"
  "msg/FollowPolicy.msg"
  "msg/MotionPhase.msg"
  "msg/HmmdDetection.msg"
  "msg/GraspCandidate.msg"
  "msg/GraspCandidates.msg"
  "action/ExecuteTask.action"
  "action/ExecuteArm.action"
  DEPENDENCIES geometry_msgs std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
