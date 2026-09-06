#include "differential_drive.h"
#include <math.h>
bool hr_diff_inverse(float vx, float wz, float track, HrWheelTargets *out) {
    if (out == 0 || !isfinite(vx) || !isfinite(wz) || !isfinite(track) || track <= 0.0f) return false;
    out->left_mps = vx - wz * track * 0.5f;
    out->right_mps = vx + wz * track * 0.5f;
    return true;
}
