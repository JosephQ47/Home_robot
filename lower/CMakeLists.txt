cmake_minimum_required(VERSION 3.16)
project(home_robot_lower_core C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
add_library(hr_lower_core
  Components/Src/crc16.c Components/Src/endian_codec.c
  Components/Src/ramp_limiter.c Components/Src/differential_drive.c
  Protocol/Src/protocol_parser.c Protocol/Src/protocol_serializer.c
  Protocol/Src/protocol_validate.c Protocol/Src/protocol_messages.c
  Application/Src/control_arbiter.c Application/Src/safety_state_machine.c
  Application/Src/command_task.c Application/Src/chassis_task.c
  Application/Src/imu_task.c Application/Src/monitor_task.c
  Application/Src/status_snapshot.c Application/Src/ipc_objects.c Application/Src/app_init.c)
target_include_directories(hr_lower_core PUBLIC Components/Inc Protocol/Inc Application/Inc Config BSP/Inc Devices/Inc)
target_compile_options(hr_lower_core PRIVATE -Wall -Wextra -Werror -Wconversion -Wshadow)
enable_testing()
add_executable(lower_core_tests Tests/Unit/test_lower_core.c)
target_link_libraries(lower_core_tests PRIVATE hr_lower_core m)
target_compile_options(lower_core_tests PRIVATE -Wall -Wextra -Werror)
add_test(NAME lower_core_tests COMMAND lower_core_tests)
