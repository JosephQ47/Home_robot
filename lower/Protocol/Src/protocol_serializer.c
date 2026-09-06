#include "protocol_serializer.h"
#include "crc16.h"
#include "endian_codec.h"
size_t hr_protocol_serialize(uint8_t id, uint16_t seq, uint32_t stamp, const uint8_t *payload, uint16_t len, uint8_t *out, size_t cap) {
    const size_t total = HR_FRAME_FIXED_SIZE + (size_t)len;
    if (out == 0 || len > HR_PROTOCOL_MAX_PAYLOAD || cap < total || (len > 0u && payload == 0)) return 0u;
    out[0]=HR_SOF0; out[1]=HR_SOF1; out[2]=HR_PROTOCOL_VERSION; out[3]=id;
    hr_write_u16_le(&out[4], len); hr_write_u16_le(&out[6], seq); hr_write_u32_le(&out[8], stamp);
    for (uint16_t i=0; i<len; ++i) out[12u+i]=payload[i];
    hr_write_u16_le(&out[12u+len], hr_crc16_ccitt_false(&out[2], 10u+(size_t)len));
    return total;
}
