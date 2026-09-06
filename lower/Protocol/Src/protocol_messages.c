#include "protocol_messages.h"
#include "endian_codec.h"
HrProtocolResult hr_decode_cmd_motion(const HrFrameView *f,HrCmdMotion *out) {
    if(f==0 || out==0 || f->message_id!=HR_MSG_CMD_MOTION) return HR_PROTOCOL_BAD_MESSAGE;
    if(f->payload_length!=HR_CMD_MOTION_PAYLOAD_SIZE || f->payload[9]!=0u || f->payload[8]>1u) return HR_PROTOCOL_BAD_LENGTH;
    out->vx_mm_s=hr_read_i32_le(&f->payload[0]); out->wz_mrad_s=hr_read_i32_le(&f->payload[4]); out->enable=f->payload[8]==1u; return HR_PROTOCOL_OK;
}
void hr_encode_cmd_motion_payload(uint8_t p[HR_CMD_MOTION_PAYLOAD_SIZE],const HrCmdMotion *cmd) { hr_write_i32_le(&p[0],cmd->vx_mm_s);hr_write_i32_le(&p[4],cmd->wz_mrad_s);p[8]=cmd->enable?1u:0u;p[9]=0u; }
