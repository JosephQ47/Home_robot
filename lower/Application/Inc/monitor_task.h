#ifndef HR_MONITOR_TASK_H
#define HR_MONITOR_TASK_H
#include "safety_state_machine.h"
typedef struct { HrSafetyMachine safety_machine; } HrMonitorTaskContext;
void monitor_task_init(HrMonitorTaskContext *context);
Safety_State_t monitor_task_step(HrMonitorTaskContext *context,const HrSafetyInputs *inputs,uint32_t now_ms);
#endif
