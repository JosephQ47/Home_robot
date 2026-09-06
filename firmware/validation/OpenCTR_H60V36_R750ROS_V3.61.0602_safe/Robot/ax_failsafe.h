#ifndef __AX_FAILSAFE_H
#define __AX_FAILSAFE_H
#include <stdint.h>
#define AX_FAILSAFE_CTL_ROS 0x00u
#define AX_FAILSAFE_TIMEOUT_TICKS 10u
void AX_FAILSAFE_Init(void);
void AX_FAILSAFE_OnRosCommand(void);
void AX_FAILSAFE_Update20ms(uint8_t control_mode, short *vx, short *vy, short *wz);
uint8_t AX_FAILSAFE_IsRosCommandFresh(void);
#endif
