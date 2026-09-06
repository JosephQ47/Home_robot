#include "chassis_task.h"
#include "ramp_limiter.h"
static float clampf(float x,float limit){return x>limit?limit:(x<-limit?-limit:x);}
bool chassis_task_step(HrChassisConfig *c,const CommandState_t *cmd,const Safety_State_t *safe,float dt,HrWheelTargets *out){
    if(out==0)return false;
    out->left_mps=0.0f;
    out->right_mps=0.0f;
    if(c==0||cmd==0||safe==0||!c->configured||c->track_width_m<=0.0f||c->max_vx_mps<=0.0f||c->max_wz_rps<=0.0f)return false;
    if(!safe->control_enable){c->vx_now=0.0f;c->wz_now=0.0f;return true;}
    float vx=0.0f,wz=0.0f;if(safe->control_enable&&cmd->valid&&cmd->enable){vx=clampf(cmd->vx_mps,c->max_vx_mps);wz=clampf(cmd->wz_rps,c->max_wz_rps);}
    c->vx_now=hr_ramp_step(c->vx_now,vx,c->accel_mps2,c->decel_mps2,dt);c->wz_now=hr_ramp_step(c->wz_now,wz,c->accel_mps2,c->decel_mps2,dt);
    return hr_diff_inverse(c->vx_now,c->wz_now,c->track_width_m,out);
}
