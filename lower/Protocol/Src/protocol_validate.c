#include "protocol_validate.h"
#include "protocol_config.h"
bool hr_sequence_is_newer(uint16_t candidate, uint16_t previous) { return candidate!=previous && (uint16_t)(candidate-previous)<0x8000u; }
HrProtocolResult hr_validate_command_freshness(uint16_t seq,uint16_t prev,bool have_prev,uint32_t stamp,uint32_t now,uint32_t max_age) {
    if(have_prev && !hr_sequence_is_newer(seq,prev)) return HR_PROTOCOL_STALE_SEQUENCE;
    const int32_t age_ms=(int32_t)(now-stamp);
    if(age_ms<-(int32_t)HR_PROTOCOL_FUTURE_TOLERANCE_MS || age_ms>(int32_t)max_age) return HR_PROTOCOL_STALE_TIMESTAMP;
    return HR_PROTOCOL_OK;
}
