#include "imu_task.h"
#include <string.h>
void imu_task_publish_invalid(ImuSample_t *s,uint32_t stamp){uint32_t seq=s?s->seq+1u:0u;if(s!=0){memset(s,0,sizeof(*s));s->seq=seq;s->stamp_us=stamp;s->quat_wxyz[0]=1.0f;s->mag_degraded=true;}}
