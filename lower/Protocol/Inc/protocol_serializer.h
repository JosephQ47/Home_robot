#ifndef HR_PROTOCOL_SERIALIZER_H
#define HR_PROTOCOL_SERIALIZER_H
#include "protocol_types.h"
size_t hr_protocol_serialize(uint8_t message_id, uint16_t sequence, uint32_t timestamp_ms, const uint8_t *payload, uint16_t payload_length, uint8_t *output, size_t output_capacity);
#endif
