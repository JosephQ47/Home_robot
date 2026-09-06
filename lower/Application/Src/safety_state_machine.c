#include "safety_state_machine.h"
#include "task_config.h"
#include <string.h>
void hr_safety_init(HrSafetyMachine *machine){if(machine!=0)memset(machine,0,sizeof(*machine));}
Safety_State_t hr_safety_step(HrSafetyMachine *machine,const HrSafetyInputs *in,uint32_t now){
    Safety_State_t out={0};out.stamp_ms=now;
    if(machine==0||in==0){out.active_faults=HR_FAULT_TASK;out.latched_faults=HR_FAULT_TASK;return out;}
    if(in->estop_active)out.active_faults|=HR_FAULT_ESTOP;
    if(!in->all_motors_online)out.active_faults|=HR_FAULT_MOTOR;
    if(!in->imu_valid)out.active_faults|=HR_FAULT_IMU;
    if(!in->command_seen||!in->chassis_seen||!in->imu_seen||
       (uint32_t)(now-in->heartbeat.command_ms)>HR_TASK_HEARTBEAT_TIMEOUT_MS||
       (uint32_t)(now-in->heartbeat.chassis_ms)>HR_TASK_HEARTBEAT_TIMEOUT_MS||
       (uint32_t)(now-in->heartbeat.imu_ms)>HR_TASK_HEARTBEAT_TIMEOUT_MS)out.active_faults|=HR_FAULT_TASK;
    if(out.active_faults!=0u)machine->latched_faults|=out.active_faults;
    else if(in->clear_fault_request)machine->latched_faults=0u;
    out.latched_faults=machine->latched_faults;
    out.control_enable=out.active_faults==0u&&out.latched_faults==0u;
    out.watchdog_gate_ok=(out.active_faults&HR_FAULT_TASK)==0u;return out;
}
