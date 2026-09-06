#ifndef HR_APP_TYPES_H
#define HR_APP_TYPES_H
#include <stdbool.h>
#include <stdint.h>
typedef enum { HR_CONTROL_NONE=0, HR_CONTROL_UPPER=1, HR_CONTROL_REMOTE=2 } HrControlSource;
typedef enum { HR_FAULT_NONE=0, HR_FAULT_ESTOP=1u<<0, HR_FAULT_TASK=1u<<1, HR_FAULT_MOTOR=1u<<2, HR_FAULT_IMU=1u<<3 } HrFaultBits;
typedef struct { float vx_mps; float wz_rps; bool enable; bool valid; uint16_t sequence; uint32_t stamp_ms; HrControlSource source; } CommandState_t;
typedef struct { bool link_valid; bool takeover; bool estop; bool sticks_centered; float vx_mps; float wz_rps; uint32_t stamp_ms; } RemoteCandidate_t;
typedef struct { bool control_enable; uint32_t active_faults; uint32_t latched_faults; bool watchdog_gate_ok; uint32_t stamp_ms; } Safety_State_t;
typedef struct { uint32_t command_ms; uint32_t chassis_ms; uint32_t imu_ms; } TaskHeartbeat_t;
typedef struct { float vx_mps; float wz_rps; uint32_t stamp_ms; bool valid; } Chassis_State_t;
typedef struct { uint32_t seq; uint32_t stamp_us; float accel_mps2[3]; float gyro_rps[3]; float quat_wxyz[4]; float mag_uT[3]; bool imu_valid; bool mag_valid; bool mag_degraded; } ImuSample_t;
#endif
