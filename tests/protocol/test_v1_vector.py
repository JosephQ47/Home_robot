import json
from pathlib import Path
import struct
import unittest


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


class ProtocolVectorTest(unittest.TestCase):
    def test_cmd_motion_vector(self):
        root = Path(__file__).resolve().parents[2]
        vector = json.loads((root / "lower/Tests/Vectors/cmd_motion_v1.json").read_text())
        frame = bytes.fromhex(vector["frame_hex"])
        self.assertEqual(frame[:2], b"\xA5\x5A")
        version, message_id, length, sequence, stamp = struct.unpack_from("<BBHHI", frame, 2)
        self.assertEqual((version, message_id, length), (1, 1, 10))
        self.assertEqual((sequence, stamp), (vector["sequence"], vector["timestamp_ms"]))
        vx, wz, enable, reserved = struct.unpack_from("<iiBB", frame, 12)
        self.assertEqual((vx, wz, bool(enable), reserved),
                         (vector["vx_mm_s"], vector["wz_mrad_s"], vector["enable"], 0))
        self.assertEqual(struct.unpack_from("<H", frame, len(frame) - 2)[0],
                         crc16_ccitt_false(frame[2:-2]))


if __name__ == "__main__":
    unittest.main()
