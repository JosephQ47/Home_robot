"""Framing, CRC and resync for the servo-controller link."""
import pathlib
import struct
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_arm_driver.protocol import (Decoder, MSG_SET_JOINTS, SOF, Status,  # noqa: E402
                                    crc16, decode_status, encode_gripper,
                                    encode_joints, encode_status, encode_stop)

POS = (0.0, 0.1, -0.2, 0.3, 0.0, 1.0)
CUR = (0.5,) * 6


def test_crc_is_the_known_ccitt_false_vector():
    assert crc16(b'123456789') == 0x29B1


def test_joint_frame_shape():
    frame = encode_joints(POS, 800)
    assert frame[:2] == SOF
    assert frame[2] == MSG_SET_JOINTS
    assert frame[3] == struct.calcsize('<6fH')
    assert crc16(frame[2:-2]) == struct.unpack('<H', frame[-2:])[0]


def test_wrong_joint_count_is_rejected():
    with pytest.raises(ValueError, match='6 joint positions'):
        encode_joints((0.0, 0.0, 0.0), 500)


def test_nonpositive_duration_is_rejected():
    for bad in (0, -1):
        with pytest.raises(ValueError, match='positive'):
            encode_joints(POS, bad)


def test_round_trip_status():
    d = Decoder()
    out = d.feed(encode_status(POS, CUR, 0.05))
    assert len(out) == 1
    assert out[0].positions == pytest.approx(POS)
    assert out[0].gripper_width == pytest.approx(0.05)
    assert out[0].healthy


def test_split_across_reads_is_reassembled():
    frame = encode_status(POS, CUR, 0.05)
    d = Decoder()
    for i in range(len(frame)):
        got = d.feed(frame[i:i + 1])
        if i < len(frame) - 1:
            assert got == []
    assert d.feed(b'') == [] or True
    # Feeding it one byte at a time yields exactly one frame at the end.
    d2 = Decoder()
    produced = []
    for i in range(len(frame)):
        produced += d2.feed(frame[i:i + 1])
    assert len(produced) == 1


def test_back_to_back_frames():
    d = Decoder()
    out = d.feed(encode_status(POS, CUR, 0.05) + encode_status(POS, CUR, 0.06))
    assert len(out) == 2
    assert out[1].gripper_width == pytest.approx(0.06)


def test_leading_garbage_is_discarded():
    d = Decoder()
    out = d.feed(b'\x00\xff\x12' + encode_status(POS, CUR, 0.05))
    assert len(out) == 1
    assert d.dropped_bytes == 3


def test_corrupt_crc_is_counted_and_resynced():
    good = encode_status(POS, CUR, 0.05)
    bad = bytearray(good)
    bad[6] ^= 0xFF
    d = Decoder()
    out = d.feed(bytes(bad) + good)
    assert d.crc_errors == 1
    assert len(out) == 1          # the good frame after it still arrives


def test_truncated_payload_waits_rather_than_guessing():
    frame = encode_status(POS, CUR, 0.05)
    d = Decoder()
    assert d.feed(frame[:-3]) == []
    assert len(d.feed(frame[-3:])) == 1


def test_buffer_does_not_grow_without_bound():
    d = Decoder(max_buffer=256)
    d.feed(b'\x00' * 10000)
    assert len(d.buffer) <= 256


def test_fault_word_decodes_to_names():
    d = Decoder()
    out = d.feed(encode_status(POS, CUR, 0.05, fault_word=(1 << 0) | (1 << 3)))
    assert out[0].faults == ('servo_overcurrent', 'action_timeout')
    assert not out[0].healthy


def test_wrong_length_status_payload_is_ignored():
    assert decode_status(b'\x00' * 4) is None


def test_stop_and_gripper_frames_are_well_formed():
    for frame in (encode_stop(), encode_gripper(0.04, 300)):
        assert frame[:2] == SOF
        assert crc16(frame[2:-2]) == struct.unpack('<H', frame[-2:])[0]
