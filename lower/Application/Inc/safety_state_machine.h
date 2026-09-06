#ifndef HR_SAFETY_STATE_MACHINE_H
#define HR_SAFETY_STATE_MACHINE_H
#include "app_types.h"
typedef struct { bool estop_active; bool all_motors_online; bool imu_valid; bool clear_fault_request; bool command_seen; bool chassis_seen; bool imu_seen; TaskHeartbeat_t heartbeat; } HrSafetyInputs;
typedef struct { uint32_t latched_faults; } HrSafetyMachine;
void hr_safety_init(HrSafetyMachine *machine);
Safety_State_t hr_safety_step(HrSafetyMachine *machine,const HrSafetyInputs *inputs,uint32_t now_ms);
#endif
