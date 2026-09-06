#include <assert.h>
#include "ax_failsafe.h"
int main(void) {
    short vx=100,vy=20,wz=-50;
    AX_FAILSAFE_Init();
    AX_FAILSAFE_Update20ms(AX_FAILSAFE_CTL_ROS,&vx,&vy,&wz);
    assert(vx==0&&vy==0&&wz==0);
    vx=100;vy=20;wz=-50;AX_FAILSAFE_OnRosCommand();
    for(unsigned i=0;i<AX_FAILSAFE_TIMEOUT_TICKS-1u;i++) AX_FAILSAFE_Update20ms(AX_FAILSAFE_CTL_ROS,&vx,&vy,&wz);
    assert(vx==100&&vy==20&&wz==-50&&AX_FAILSAFE_IsRosCommandFresh());
    AX_FAILSAFE_Update20ms(AX_FAILSAFE_CTL_ROS,&vx,&vy,&wz);
    assert(vx==0&&vy==0&&wz==0&&!AX_FAILSAFE_IsRosCommandFresh());
    vx=77;AX_FAILSAFE_Update20ms(1u,&vx,&vy,&wz);assert(vx==77);
    return 0;
}
