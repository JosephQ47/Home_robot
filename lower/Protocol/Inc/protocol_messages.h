#ifndef HR_PROTOCOL_MESSAGES_H
#define HR_PROTOCOL_MESSAGES_H
#include <stdbool.h>
#include <stdint.h>
#include "protocol_types.h"
#define HR_CMD_MOTION_PAYLOAD_SIZE 10u
typedef struct { int32_t vx_mm_s; int32_t wz_mrad_s; bool enable; } HrCmdMotion;
HrProtocolResult hr_decode_cmd_motion(const HrFrameView *frame, HrCmdMotion *out);
void hr_encode_cmd_motion_payload(uint8_t payload[HR_CMD_MOTION_PAYLOAD_SIZE], const HrCmdMotion *cmd);
#endif
