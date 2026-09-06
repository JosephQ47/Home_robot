#include "control_arbiter.h"
#include "protocol_config.h"
#include <string.h>
void hr_control_arbiter_init(HrControlArbiter *a){memset(a,0,sizeof(*a));}
static CommandState_t zero_command(uint32_t now){CommandState_t c={0};c.stamp_ms=now;return c;}
CommandState_t hr_control_arbiter_step(HrControlArbiter *a,const Safety_State_t *s,const CommandState_t *u,const RemoteCandidate_t *r,uint32_t now){
    CommandState_t out=zero_command(now);
    if(a==0||s==0||u==0||r==0||!s->control_enable||r->estop)return out;
    if(r->takeover){
        if(!a->remote_selected){a->remote_selected=true;a->remote_armed=false;}
        if(!r->link_valid || (uint32_t)(now-r->stamp_ms)>HR_REMOTE_COMMAND_TIMEOUT_MS)return out;
        if(!a->remote_armed){if(r->sticks_centered)a->remote_armed=true;return out;}
        out.vx_mps=r->vx_mps;out.wz_rps=r->wz_rps;out.enable=true;out.valid=true;out.source=HR_CONTROL_REMOTE;out.stamp_ms=r->stamp_ms;return out;
    }
    if(a->remote_selected){a->remote_selected=false;a->remote_armed=false;return out;}
    if(u->valid&&u->enable&&(uint32_t)(now-u->stamp_ms)<=HR_UPPER_COMMAND_TIMEOUT_MS)return *u;
    return out;
}
