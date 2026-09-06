#ifndef HR_STATUS_SNAPSHOT_H
#define HR_STATUS_SNAPSHOT_H
#include "app_types.h"
typedef struct { uint32_t sequence; Chassis_State_t chassis; ImuSample_t imu; Safety_State_t safety; } Robot_Status_t;
void status_snapshot_zero(Robot_Status_t *status);
#endif
