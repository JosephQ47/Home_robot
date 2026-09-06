#include "protocol_parser.h"
#include "crc16.h"
#include "endian_codec.h"
void hr_protocol_parser_init(HrProtocolParser *p) { p->used=0u; p->expected=0u; p->bad_frames=0u; }
static void restart(HrProtocolParser *p, uint8_t byte) { p->used=byte==HR_SOF0?1u:0u; if(p->used==1u)p->bytes[0]=byte; p->expected=0u; }
bool hr_protocol_parser_feed(HrProtocolParser *p, uint8_t byte, HrFrameView *out) {
    if (p==0 || out==0) return false;
    if (p->used==0u) { restart(p,byte); return false; }
    if (p->used==1u) { if(byte!=HR_SOF1){restart(p,byte);return false;} p->bytes[p->used++]=byte; return false; }
    if (p->used>=HR_FRAME_MAX_SIZE) { ++p->bad_frames; restart(p,byte); return false; }
    p->bytes[p->used++]=byte;
    if (p->used==6u) { const uint16_t len=hr_read_u16_le(&p->bytes[4]); if(len>HR_PROTOCOL_MAX_PAYLOAD){++p->bad_frames;restart(p,byte);return false;} p->expected=HR_FRAME_FIXED_SIZE+(size_t)len; }
    if (p->expected==0u || p->used<p->expected) return false;
    const uint16_t len=hr_read_u16_le(&p->bytes[4]);
    const uint16_t got=hr_read_u16_le(&p->bytes[12u+len]);
    const uint16_t want=hr_crc16_ccitt_false(&p->bytes[2],10u+(size_t)len);
    if(p->bytes[2]!=HR_PROTOCOL_VERSION || got!=want){++p->bad_frames;p->used=0u;p->expected=0u;return false;}
    out->version=p->bytes[2]; out->message_id=p->bytes[3]; out->payload_length=len; out->sequence=hr_read_u16_le(&p->bytes[6]); out->timestamp_ms=hr_read_u32_le(&p->bytes[8]); out->payload=&p->bytes[12];
    p->used=0u; p->expected=0u; return true;
}
