#include "endian_codec.h"
uint16_t hr_read_u16_le(const uint8_t *p) { return (uint16_t)(p[0] | ((uint16_t)p[1] << 8)); }
uint32_t hr_read_u32_le(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
int32_t hr_read_i32_le(const uint8_t *p) { return (int32_t)hr_read_u32_le(p); }
void hr_write_u16_le(uint8_t *p, uint16_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); }
void hr_write_u32_le(uint8_t *p, uint32_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); p[2]=(uint8_t)(v>>16); p[3]=(uint8_t)(v>>24); }
void hr_write_i32_le(uint8_t *p, int32_t v) { hr_write_u32_le(p, (uint32_t)v); }
