#include "crc16.h"
uint16_t hr_crc16_ccitt_false(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < length; ++i) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (uint8_t bit = 0; bit < 8u; ++bit) {
            uint32_t shifted = (uint32_t)crc << 1;
            if ((crc & 0x8000u) != 0u) shifted ^= 0x1021u;
            crc = (uint16_t)(shifted & 0xFFFFu);
        }
    }
    return crc;
}
