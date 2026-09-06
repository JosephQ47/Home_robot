#ifndef HR_COMMAND_TASK_H
#define HR_COMMAND_TASK_H
#include "app_types.h"
#include "control_arbiter.h"
#include "protocol_types.h"
typedef struct { CommandState_t upper; bool have_sequence; uint16_t last_sequence; HrControlArbiter arbiter; uint32_t rejected_frames; } HrCommandTaskContext;
void command_task_init(HrCommandTaskContext *context);
HrProtocolResult command_task_accept_frame(HrCommandTaskContext *context,const HrFrameView *frame,uint32_t now_ms);
CommandState_t command_task_step(HrCommandTaskContext *context,const Safety_State_t *safety,const RemoteCandidate_t *remote,uint32_t now_ms);
#endif
