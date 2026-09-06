#ifndef HR_RAMP_LIMITER_H
#define HR_RAMP_LIMITER_H
float hr_ramp_step(float current, float target, float accel_limit, float decel_limit, float dt_s);
#endif
