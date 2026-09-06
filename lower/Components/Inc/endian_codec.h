#ifndef HR_ENDIAN_CODEC_H
#define HR_ENDIAN_CODEC_H
#include <stdint.h>
uint16_t hr_read_u16_le(const uint8_t *p);
uint32_t hr_read_u32_le(const uint8_t *p);
int32_t hr_read_i32_le(const uint8_t *p);
void hr_write_u16_le(uint8_t *p, uint16_t value);
void hr_write_u32_le(uint8_t *p, uint32_t value);
void hr_write_i32_le(uint8_t *p, int32_t value);
#endif
