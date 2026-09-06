#include "ramp_limiter.h"
#include <math.h>
float hr_ramp_step(float current, float target, float accel, float decel, float dt) {
    if (!isfinite(current) || !isfinite(target) || accel <= 0.0f || decel <= 0.0f || dt <= 0.0f) return 0.0f;
    const float rate = fabsf(target) < fabsf(current) ? decel : accel;
    const float max_delta = rate * dt;
    const float delta = target - current;
    if (delta > max_delta) return current + max_delta;
    if (delta < -max_delta) return current - max_delta;
    return target;
}
