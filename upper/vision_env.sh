#!/usr/bin/env bash
# Source this file before building or launching PC vision nodes.
_hr_upper="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HR_VISION_HOME="${HR_VISION_HOME:-/home/luckfox/Hi3516}"
source /opt/ros/humble/setup.bash
if [ -d "$HR_VISION_HOME/ros-deps/root/opt/ros/humble" ]; then
    _hr_deps="$HR_VISION_HOME/ros-deps/root/opt/ros/humble"
    export AMENT_PREFIX_PATH="$_hr_deps:${AMENT_PREFIX_PATH:-}"
    export CMAKE_PREFIX_PATH="$_hr_deps:${CMAKE_PREFIX_PATH:-}"
    export LD_LIBRARY_PATH="$_hr_deps/lib:${LD_LIBRARY_PATH:-}"
    export PYTHONPATH="$_hr_deps/local/lib/python3.10/dist-packages:${PYTHONPATH:-}"
fi
source "$HR_VISION_HOME/vision-venv/bin/activate"
export YOLO_CONFIG_DIR="$HR_VISION_HOME/vision-assets/settings"
if [ -f "$_hr_upper/install/local_setup.bash" ]; then
    source "$_hr_upper/install/local_setup.bash"
fi
unset _hr_upper _hr_deps
