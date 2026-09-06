#ifndef HR_CHASSIS_TASK_H
#define HR_CHASSIS_TASK_H
#include "app_types.h"
#include "differential_drive.h"
typedef struct { float track_width_m; float max_vx_mps; float max_wz_rps; float accel_mps2; float decel_mps2; float vx_now; float wz_now; bool configured; } HrChassisConfig;
bool chassis_task_step(HrChassisConfig *config,const CommandState_t *command,const Safety_State_t *safety,float dt_s,HrWheelTargets *targets);
#endif
