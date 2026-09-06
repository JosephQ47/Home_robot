#ifndef HR_PROTOCOL_VALIDATE_H
#define HR_PROTOCOL_VALIDATE_H
#include <stdbool.h>
#include "protocol_types.h"
bool hr_sequence_is_newer(uint16_t candidate, uint16_t previous);
HrProtocolResult hr_validate_command_freshness(uint16_t sequence, uint16_t previous_sequence, bool have_previous, uint32_t timestamp_ms, uint32_t now_ms, uint32_t max_age_ms);
#endif
