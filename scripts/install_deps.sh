#!/usr/bin/env bash
# Upstream ROS 2 packages this workspace needs but does not vendor.
#
# Run once on a fresh machine. It only installs; it changes nothing in the repo.
# Every package here is named by a launch file or a package.xml exec_depend, so
# a missing one shows up as a node that refuses to start rather than as a node
# that starts and behaves oddly.
set -euo pipefail

ROS_DISTRO="${ROS_DISTRO:-humble}"

# --- required for the navigation and localization chain -----------------------
CORE=(
  "ros-${ROS_DISTRO}-robot-localization"      # EKF: /odometry/filtered + odom->base_link
  "ros-${ROS_DISTRO}-slam-toolbox"            # mapping mode
  "ros-${ROS_DISTRO}-nav2-bringup"
  "ros-${ROS_DISTRO}-nav2-amcl"
  "ros-${ROS_DISTRO}-nav2-map-server"
  "ros-${ROS_DISTRO}-nav2-lifecycle-manager"
  "ros-${ROS_DISTRO}-nav2-controller"
  "ros-${ROS_DISTRO}-nav2-planner"
  "ros-${ROS_DISTRO}-nav2-behaviors"
  "ros-${ROS_DISTRO}-nav2-bt-navigator"
  "ros-${ROS_DISTRO}-nav2-waypoint-follower"
  "ros-${ROS_DISTRO}-nav2-dwb-controller"
  "ros-${ROS_DISTRO}-nav2-collision-monitor"  # the laser stop zone
  "ros-${ROS_DISTRO}-vision-msgs"             # Detection2DArray, used by perception
)

# --- required for AprilTag docking -------------------------------------------
DOCKING=(
  "ros-${ROS_DISTRO}-apriltag"
  "ros-${ROS_DISTRO}-apriltag-ros"
  "ros-${ROS_DISTRO}-apriltag-msgs"
  "ros-${ROS_DISTRO}-opennav-docking"
  "ros-${ROS_DISTRO}-opennav-docking-msgs"
)

# --- hardware drivers; only needed once the devices are fitted ----------------
# sllidar_ros2 (Slamtec's own driver, the one that supports the S3) is NOT in
# apt and must be cloned into upper/src. rplidar_ros is the older packaged
# driver and does not cover the S3, so it is deliberately not substituted here.
HARDWARE=(
  "ros-${ROS_DISTRO}-realsense2-camera"       # wrist D435i
)

# --- optional Python extras ---------------------------------------------------
# pyserial: hr_arm_driver with transport=serial (transport=mock needs nothing)
# vosk + sounddevice: hr_voice_capture with asr_adapter=vosk
PYTHON_EXTRAS=(pyserial vosk sounddevice)

usage() {
  cat <<'USAGE'
usage: scripts/install_deps.sh [core|docking|hardware|python|all]

  core      navigation, localization and perception message packages
  docking   AprilTag detection and OpenNav Docking
  hardware  RPLIDAR S3 and RealSense drivers (only once the devices exist)
  python    pyserial / vosk / sounddevice, via pip
  all       everything above (default)

Two drivers are NOT in this list because they are not in apt:

  Orbbec Gemini 2   build from Orbbec's SDK; see docs/features/hr_camera_gemini2.md
  RPLIDAR S3        git clone -b humble https://github.com/Slamtec/sllidar_ros2
                    into upper/src, then colcon build
USAGE
}

install_apt() {
  local -n packages=$1
  echo "==> apt install ${#packages[@]} packages"
  sudo apt-get update
  sudo apt-get install -y "${packages[@]}"
}

target="${1:-all}"
case "$target" in
  core)     install_apt CORE ;;
  docking)  install_apt DOCKING ;;
  hardware) install_apt HARDWARE ;;
  python)   python3 -m pip install --user "${PYTHON_EXTRAS[@]}" ;;
  all)
    all=("${CORE[@]}" "${DOCKING[@]}" "${HARDWARE[@]}")
    install_apt all
    python3 -m pip install --user "${PYTHON_EXTRAS[@]}" || \
      echo "note: pip extras failed; they are only needed for serial arm and vosk voice"
    ;;
  -h|--help) usage; exit 0 ;;
  *) usage; exit 1 ;;
esac

echo
echo "==> done. Rebuild and re-source the overlay:"
echo "    cd upper && colcon build && source install/setup.bash"
