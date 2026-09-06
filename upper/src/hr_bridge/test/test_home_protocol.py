import json
from pathlib import Path
from hr_bridge.home_protocol import CMD_MOTION, Parser, encode_motion


VECTOR = "lower/Tests/Vectors/cmd_motion_v1.json"


def find_vector():
    """向上搜索定位共享测试向量，不用固定的 parents[N]。

    这份向量是 C 与 Python 两端共用的，必须能被两边找到。原来写死
    parents[5]，工作空间从 upper/ros2_ws/src 挪到 upper/src（技术方案 §9.2）
    后就少了一层，测试直接 FileNotFoundError。层数是隐式耦合，目录一动就断，
    改为向上找到为止。
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / VECTOR
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"未能在任何上级目录找到 {VECTOR}")


def test_shared_cmd_motion_vector_and_fragmented_parse():
    vector = json.loads(find_vector().read_text())
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
