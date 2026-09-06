"""Parser for the official HMMD report-mode frame (little endian)."""
from dataclasses import dataclass
import struct

HEAD = b'\xF4\xF3\xF2\xF1'
TAIL = b'\xF8\xF7\xF6\xF5'

# Command 0x0012 selects the module output mode.  The official documentation
# defines value 4 as report mode.  In that mode the module emits binary frames
# containing presence, target distance and 16 range-gate energy values.
REPORT_MODE_COMMAND = bytes.fromhex(
    'FD FC FB FA 08 00 12 00 00 00 04 00 00 00 04 03 02 01'
)


@dataclass(frozen=True)
class Detection:
    presence: bool
    range_raw: int
    energy: tuple[int, ...]


class Parser:
    def __init__(self):
        self.buffer = bytearray(); self.bad_frames = 0

    def feed(self, data):
        self.buffer.extend(data); output = []
        while True:
            start = self.buffer.find(HEAD)
            if start < 0:
                self.buffer[:] = self.buffer[-3:]; break
            if start: del self.buffer[:start]
            if len(self.buffer) < 6: break
            payload_len = struct.unpack_from('<H', self.buffer, 4)[0]
            total = 4 + 2 + payload_len + 4
            if payload_len < 3 or payload_len > 256:
                self.bad_frames += 1; del self.buffer[:4]; continue
            if len(self.buffer) < total: break
            frame = bytes(self.buffer[:total]); del self.buffer[:total]
            if frame[-4:] != TAIL:
                self.bad_frames += 1; continue
            payload = frame[6:-4]
            if len(payload) < 35:
                self.bad_frames += 1; continue
            output.append(Detection(payload[0] == 1, struct.unpack_from('<H', payload, 1)[0],
                                    struct.unpack_from('<16H', payload, 3)))
        return output
