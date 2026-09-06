#include "ax_failsafe.h"
static volatile uint8_t ros_cmd_fresh_ticks = 0u;
void AX_FAILSAFE_Init(void) { ros_cmd_fresh_ticks = 0u; }
void AX_FAILSAFE_OnRosCommand(void) { ros_cmd_fresh_ticks = AX_FAILSAFE_TIMEOUT_TICKS; }
uint8_t AX_FAILSAFE_IsRosCommandFresh(void) { return ros_cmd_fresh_ticks > 0u ? 1u : 0u; }
void AX_FAILSAFE_Update20ms(uint8_t control_mode, short *vx, short *vy, short *wz) {
    if (vx == 0 || vy == 0 || wz == 0 || control_mode != AX_FAILSAFE_CTL_ROS) return;
    if (ros_cmd_fresh_ticks > 0u) ros_cmd_fresh_ticks--;
    if (ros_cmd_fresh_ticks == 0u) { *vx = 0; *vy = 0; *wz = 0; }
}
