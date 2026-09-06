#ifndef HR_PROTOCOL_PARSER_H
#define HR_PROTOCOL_PARSER_H
#include <stdbool.h>
#include "protocol_types.h"
typedef struct { uint8_t bytes[HR_FRAME_MAX_SIZE]; size_t used; size_t expected; uint32_t bad_frames; } HrProtocolParser;
void hr_protocol_parser_init(HrProtocolParser *parser);
bool hr_protocol_parser_feed(HrProtocolParser *parser, uint8_t byte, HrFrameView *out);
#endif
