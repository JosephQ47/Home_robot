import struct

from hr_hmmd.protocol import HEAD, TAIL, Parser


def test_report_frame_split_input():
    payload = bytes([1]) + struct.pack('<H', 123) + struct.pack('<16H', *range(16))
    frame = HEAD + struct.pack('<H', len(payload)) + payload + TAIL
    parser = Parser()
    assert parser.feed(frame[:9]) == []
    result = parser.feed(frame[9:])
    assert result[0].presence and result[0].range_raw == 123 and result[0].energy[15] == 15
