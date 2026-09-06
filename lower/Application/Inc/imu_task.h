#ifndef HR_IMU_TASK_H
#define HR_IMU_TASK_H
#include "app_types.h"
void imu_task_publish_invalid(ImuSample_t *sample,uint32_t stamp_us);
#endif
