#ifndef HR_CONTROL_ARBITER_H
#define HR_CONTROL_ARBITER_H
#include "app_types.h"
typedef struct { bool remote_selected; bool remote_armed; } HrControlArbiter;
void hr_control_arbiter_init(HrControlArbiter *arbiter);
CommandState_t hr_control_arbiter_step(HrControlArbiter *arbiter,const Safety_State_t *safety,const CommandState_t *upper,const RemoteCandidate_t *remote,uint32_t now_ms);
#endif
