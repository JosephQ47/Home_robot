"""Rules DOCK-1..DOCK-7 from docs/features/hr_docking.md."""
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_docking.adapter import (DockConfig, DockPoseAdapter, Pose2D, Rejected,  # noqa: E402
                                compose, wrap_angle)

CFG = DockConfig(tag_id=7, tag_to_contact=Pose2D(0.30, 0.0, 0.0), tag_timeout_sec=0.5,
                 max_jump_xy_m=0.15, max_jump_yaw_rad=0.35, max_consecutive_jumps=3,
                 min_consecutive_detections=3)


def warmed(adapter, pose=Pose2D(1.0, 0.0, 0.0), t=0.0):
    """Feed the minimum detections so the next update publishes."""
    for i in range(CFG.min_consecutive_detections - 1):
        adapter.update(CFG.tag_id, pose, t + i * 0.05)
    return adapter


def test_wrong_tag_id_is_rejected():
    a = DockPoseAdapter(CFG)
    out = a.update(99, Pose2D(1.0, 0.0, 0.0), 0.0)
    assert isinstance(out, Rejected) and out.reason == 'tag_id_mismatch'


def test_missing_camera_info_is_rejected():
    a = DockPoseAdapter(CFG)
    out = a.update(CFG.tag_id, Pose2D(1.0, 0.0, 0.0), 0.0, camera_info_valid=False)
    assert isinstance(out, Rejected) and out.reason == 'camera_info_invalid'


def test_single_frame_does_not_publish():
    a = DockPoseAdapter(CFG)
    assert isinstance(a.update(CFG.tag_id, Pose2D(1.0, 0.0, 0.0), 0.0), Rejected)


def test_publishes_after_required_streak():
    a = warmed(DockPoseAdapter(CFG))
    out = a.update(CFG.tag_id, Pose2D(1.0, 0.0, 0.0), 0.1)
    assert isinstance(out, Pose2D)


def test_contact_offset_is_applied_in_tag_frame():
    a = warmed(DockPoseAdapter(CFG), Pose2D(1.0, 0.0, math.pi / 2))
    out = a.update(CFG.tag_id, Pose2D(1.0, 0.0, math.pi / 2), 0.1)
    # Tag faces +y, so a 0.30 m forward offset lands at (1.0, 0.30).
    assert math.isclose(out.x, 1.0, abs_tol=1e-9)
    assert math.isclose(out.y, 0.30, abs_tol=1e-9)


def test_pose_jump_is_rejected_then_latches():
    a = warmed(DockPoseAdapter(CFG))
    a.update(CFG.tag_id, Pose2D(1.0, 0.0, 0.0), 0.1)
    for _ in range(CFG.max_consecutive_jumps - 1):
        out = a.update(CFG.tag_id, Pose2D(5.0, 0.0, 0.0), 0.2)
        assert isinstance(out, Rejected) and out.reason == 'pose_jump'
    out = a.update(CFG.tag_id, Pose2D(5.0, 0.0, 0.0), 0.3)
    assert isinstance(out, Rejected) and out.reason == 'pose_jump_latched'
    assert a.failed
    # Latched means latched: even a perfect detection is refused afterwards.
    assert isinstance(a.update(CFG.tag_id, Pose2D(1.0, 0.0, 0.0), 0.4), Rejected)


def test_jump_just_under_threshold_is_accepted():
    a = warmed(DockPoseAdapter(CFG))
    a.update(CFG.tag_id, Pose2D(1.0, 0.0, 0.0), 0.1)
    out = a.update(CFG.tag_id, Pose2D(1.0 + CFG.max_jump_xy_m, 0.0, 0.0), 0.2)
    assert isinstance(out, Pose2D)


def test_yaw_jump_uses_wrapped_difference():
    """-179 deg to +179 deg is a 2 deg move, not a 358 deg one."""
    a = warmed(DockPoseAdapter(CFG), Pose2D(1.0, 0.0, math.radians(-179)))
    a.update(CFG.tag_id, Pose2D(1.0, 0.0, math.radians(-179)), 0.1)
    out = a.update(CFG.tag_id, Pose2D(1.0, 0.0, math.radians(179)), 0.2)
    assert isinstance(out, Pose2D)


def test_expiry_and_no_stale_reuse():
    a = warmed(DockPoseAdapter(CFG))
    a.update(CFG.tag_id, Pose2D(1.0, 0.0, 0.0), 0.1)
    assert not a.expired(0.1 + CFG.tag_timeout_sec)
    assert a.expired(0.1 + CFG.tag_timeout_sec + 0.001)
    a.tick(10.0)
    # After ageing out, the streak restarts: no instant republish from memory.
    assert isinstance(a.update(CFG.tag_id, Pose2D(1.0, 0.0, 0.0), 10.0), Rejected)


def test_compose_is_identity_for_zero_offset():
    p = Pose2D(2.0, -1.0, 0.7)
    out = compose(p, Pose2D())
    assert (out.x, out.y) == (p.x, p.y) and math.isclose(out.yaw, p.yaw)


def test_wrap_angle_range():
    for a in (-10.0, -math.pi, 0.0, math.pi, 10.0):
        assert -math.pi - 1e-9 <= wrap_angle(a) <= math.pi + 1e-9
