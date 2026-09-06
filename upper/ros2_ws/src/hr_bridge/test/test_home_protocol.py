import json
from pathlib import Path
from hr_bridge.home_protocol import CMD_MOTION, Parser, encode_motion


def test_shared_cmd_motion_vector_and_fragmented_parse():
    root = Path(__file__).resolve().parents[5]
    vector = json.loads((root / "lower/Tests/Vectors/cmd_motion_v1.json").read_text())
    encoded = encode_motion(vector["sequence"], vector["timestamp_ms"],
                            vector["vx_mm_s"], vector["wz_mrad_s"], vector["enable"])
    assert encoded == bytes.fromhex(vector["frame_hex"])
    parser = Parser()
    assert parser.feed(b"noise" + encoded[:7]) == []
    frames = parser.feed(encoded[7:])
    assert len(frames) == 1
    assert (frames[0].message_id, frames[0].sequence, frames[0].timestamp_ms) == (
        CMD_MOTION, vector["sequence"], vector["timestamp_ms"])


def test_crc_rejection():
    damaged = bytearray(encode_motion(1, 2, 3, 4, True))
    damaged[-1] ^= 1
    parser = Parser()
    assert parser.feed(damaged) == []
    assert parser.bad_frames == 1
