import unittest
import struct

from pc_control.protocol import (
    ProtocolError,
    StateFrame,
    VelocityCommand,
    XProtocolParser,
    decode_state_frame,
    encode_frame,
    encode_velocity_frame,
)
from pc_control.serial_bridge import SerialBridge


class MemoryTransport:
    def __init__(self, incoming=b""):
        self.incoming = bytearray(incoming)
        self.writes = []

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def read_available(self):
        data = bytes(self.incoming)
        self.incoming.clear()
        return data


class ProtocolTest(unittest.TestCase):
    def test_velocity_frame_matches_pdf_layout(self):
        frame = encode_velocity_frame(VelocityCommand(1000, 0, -500))
        self.assertEqual(frame[:4], b"\xAA\x55\x0B\x50")
        self.assertEqual(frame[4:10], b"\x03\xE8\x00\x00\xFE\x0C")
        self.assertEqual(frame[-1], sum(frame[:-1]) & 0xFF)

    def test_parser_handles_noise_split_and_bad_checksum(self):
        good = encode_velocity_frame(VelocityCommand(1, 2, 3))
        parser = XProtocolParser()
        self.assertEqual(parser.feed(b"noise" + good[:4]), [])
        self.assertEqual(parser.feed(good[4:]), [good])
        bad = bytearray(good)
        bad[-1] ^= 0xFF
        self.assertEqual(parser.feed(bytes(bad)), [])
        self.assertEqual(parser.bad_frames, 1)

    def test_state_frame_decode(self):
        values = (1, 2, 3, 4, 5, 6, 100, 200, -300, 1234)
        frame = encode_frame(0x10, struct.pack(">hhhhhhhhhh", *values))
        self.assertEqual(
            decode_state_frame(frame), StateFrame((1, 2, 3), (4, 5, 6), (100, 200, -300), 1234)
        )

    def test_bridge_sends_zero_and_publishes_state(self):
        state_frame = encode_frame(0x10, struct.pack(">hhhhhhhhhh", *range(10)))
        transport = MemoryTransport(state_frame)
        bridge = SerialBridge(transport)
        bridge.send_velocity(10, 20)
        states = bridge.poll()
        bridge.stop()
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].velocity, (6, 7, 8))
        self.assertEqual(transport.writes[-1], encode_velocity_frame(VelocityCommand()))

    def test_velocity_rejects_overflow(self):
        with self.assertRaises(ProtocolError):
            encode_velocity_frame(VelocityCommand(40000))


if __name__ == "__main__":
    unittest.main()
