#ifndef HR_DIFFERENTIAL_DRIVE_H
#define HR_DIFFERENTIAL_DRIVE_H
#include <stdbool.h>
typedef struct { float left_mps; float right_mps; } HrWheelTargets;
bool hr_diff_inverse(float vx_mps, float wz_rps, float track_width_m, HrWheelTargets *out);
#endif
