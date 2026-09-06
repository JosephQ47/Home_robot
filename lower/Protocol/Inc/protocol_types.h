#ifndef HR_PROTOCOL_TYPES_H
#define HR_PROTOCOL_TYPES_H
#include <stddef.h>
#include <stdint.h>
#include "protocol_config.h"
#define HR_SOF0 0xA5u
#define HR_SOF1 0x5Au
#define HR_FRAME_FIXED_SIZE 14u
#define HR_FRAME_MAX_SIZE (HR_FRAME_FIXED_SIZE + HR_PROTOCOL_MAX_PAYLOAD)
typedef enum { HR_MSG_CMD_MOTION=0x01, HR_MSG_CMD_MODE=0x02, HR_MSG_HEARTBEAT=0x03, HR_MSG_STATE_FAST=0x81, HR_MSG_STATE_SLOW=0x82, HR_MSG_FAULT_EVENT=0x83 } HrMessageId;
typedef enum { HR_PROTOCOL_OK=0, HR_PROTOCOL_INCOMPLETE, HR_PROTOCOL_BAD_VERSION, HR_PROTOCOL_BAD_LENGTH, HR_PROTOCOL_BAD_CRC, HR_PROTOCOL_BAD_MESSAGE, HR_PROTOCOL_STALE_SEQUENCE, HR_PROTOCOL_STALE_TIMESTAMP } HrProtocolResult;
typedef struct { uint8_t version; uint8_t message_id; uint16_t payload_length; uint16_t sequence; uint32_t timestamp_ms; const uint8_t *payload; } HrFrameView;
#endif
