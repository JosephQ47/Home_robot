#include "command_task.h"
#include "protocol_config.h"
#include "protocol_messages.h"
#include "protocol_validate.h"
#include <string.h>
void command_task_init(HrCommandTaskContext *c){memset(c,0,sizeof(*c));hr_control_arbiter_init(&c->arbiter);}
HrProtocolResult command_task_accept_frame(HrCommandTaskContext *c,const HrFrameView *f,uint32_t now){
    if(c==0||f==0)return HR_PROTOCOL_BAD_MESSAGE;
    HrProtocolResult r=hr_validate_command_freshness(f->sequence,c->last_sequence,c->have_sequence,f->timestamp_ms,now,HR_UPPER_COMMAND_TIMEOUT_MS);
    if(r!=HR_PROTOCOL_OK){++c->rejected_frames;return r;}
    HrCmdMotion wire;r=hr_decode_cmd_motion(f,&wire);if(r!=HR_PROTOCOL_OK){++c->rejected_frames;return r;}
    c->upper.vx_mps=(float)wire.vx_mm_s/1000.0f;c->upper.wz_rps=(float)wire.wz_mrad_s/1000.0f;c->upper.enable=wire.enable;c->upper.valid=true;c->upper.sequence=f->sequence;c->upper.stamp_ms=now;c->upper.source=HR_CONTROL_UPPER;c->last_sequence=f->sequence;c->have_sequence=true;return HR_PROTOCOL_OK;
}
CommandState_t command_task_step(HrCommandTaskContext *c,const Safety_State_t *s,const RemoteCandidate_t *r,uint32_t now){
    if((uint32_t)(now-c->upper.stamp_ms)>HR_UPPER_COMMAND_TIMEOUT_MS){c->upper.valid=false;c->upper.enable=false;c->upper.vx_mps=0.0f;c->upper.wz_rps=0.0f;}
    return hr_control_arbiter_step(&c->arbiter,s,&c->upper,r,now);
}
