#include "monitor_task.h"
void monitor_task_init(HrMonitorTaskContext *context){if(context!=0)hr_safety_init(&context->safety_machine);}
Safety_State_t monitor_task_step(HrMonitorTaskContext *context,const HrSafetyInputs *inputs,uint32_t now){
    if(context==0){Safety_State_t invalid={0};invalid.active_faults=HR_FAULT_TASK;invalid.latched_faults=HR_FAULT_TASK;return invalid;}
    return hr_safety_step(&context->safety_machine,inputs,now);
}
