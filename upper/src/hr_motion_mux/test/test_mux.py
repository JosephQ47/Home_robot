"""Every rule MUX-1..MUX-8 from docs/features/hr_motion_mux.md gets an assertion here."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_motion_mux.mux import (DOCKING, FOLLOWING, NAVIGATING, ZERO, Limits,  # noqa: E402
                               MotionMux)

LIMITS = Limits(source_timeout_sec=0.2, phase_timeout_sec=1.0, zero_hold_sec=0.3)


def armed(phase, t=0.0, seq=1):
    """A mux already past its switch-zero window, authorising `phase`."""
    mux = MotionMux(limits=LIMITS)
    mux.on_phase(phase, seq, t)
    return mux, t + LIMITS.zero_hold_sec


def test_navigating_forwards_nav_only():
    mux, t = armed(NAVIGATING)
    mux.on_nav(0.3, 0.1, t)
    mux.on_dock(0.9, 0.9, t)
    d = mux.decide(t)
    assert (d.vx, d.wz, d.source) == (0.3, 0.1, 'nav')


def test_following_also_selects_nav():
    # FOLLOWING has no velocity source of its own; Nav2 drives the follow pose.
    mux, t = armed(FOLLOWING)
    mux.on_nav(0.2, -0.4, t)
    assert mux.decide(t).source == 'nav'


def test_docking_forwards_dock_only():
    mux, t = armed(DOCKING)
    mux.on_nav(0.9, 0.9, t)
    mux.on_dock(0.05, 0.0, t)
    d = mux.decide(t)
    assert (d.vx, d.source) == (0.05, 'dock')


def test_unauthorised_source_never_leaks():
    """MUX-7: a chatty unauthorised publisher must not reach the output."""
    mux, t = armed(NAVIGATING)
    for i in range(50):
        mux.on_dock(1.0, 1.0, t + i * 0.01)
    d = mux.decide(t + 0.5)
    assert (d.vx, d.wz) == (0.0, 0.0)


def test_zero_phase_outputs_zero():
    mux, t = armed(ZERO)
    mux.on_nav(0.5, 0.5, t)
    mux.on_dock(0.5, 0.5, t)
    d = mux.decide(t)
    assert (d.vx, d.wz, d.source) == (0.0, 0.0, None)


def test_switch_holds_zero_before_new_source():
    """MUX-2: the whole zero_hold window is zero, and the tick right after is not."""
    mux = MotionMux(limits=LIMITS)
    mux.on_phase(NAVIGATING, 1, 0.0)
    mux.on_nav(0.3, 0.0, 0.3)
    assert mux.decide(0.3).vx == 0.3
    mux.on_phase(DOCKING, 2, 0.4)
    mux.on_dock(0.1, 0.0, 0.4)
    for t in (0.4, 0.5, 0.6, 0.69):
        assert mux.decide(t).vx == 0.0, f'leaked at {t}'
    mux.on_dock(0.1, 0.0, 0.7)
    assert mux.decide(0.7).vx == 0.1


def test_zero_required_forces_hold_without_phase_change():
    mux, t = armed(NAVIGATING)
    mux.on_nav(0.3, 0.0, t)
    assert mux.decide(t).vx == 0.3
    mux.on_phase(NAVIGATING, 2, t, zero_required=True)
    assert mux.decide(t).reason == 'switch_zero_hold'


def test_stale_source_zeroes_and_does_not_reuse():
    """MUX-3: equal to the threshold still forwards; past it goes to zero."""
    mux, t = armed(NAVIGATING)
    mux.on_nav(0.3, 0.0, t)
    assert mux.decide(t + 0.2).vx == 0.3
    assert mux.decide(t + 0.2001).vx == 0.0
    # And it stays zero — the last good value is never resurrected.
    assert mux.decide(t + 5.0).vx == 0.0


def test_stale_phase_zeroes():
    mux, t = armed(NAVIGATING)
    mux.on_nav(0.3, 0.0, t + 5.0)
    d = mux.decide(t + 5.0)
    assert (d.vx, d.reason) == (0.0, 'phase_stale')


def test_rewound_or_repeated_seq_is_ignored():
    """MUX-5: a straggler from the phase we just left must not re-authorise it."""
    mux = MotionMux(limits=LIMITS)
    mux.on_phase(DOCKING, 7, 0.0)
    assert mux.on_phase(NAVIGATING, 7, 0.1) is False
    assert mux.on_phase(NAVIGATING, 3, 0.1) is False
    assert mux.phase == DOCKING
    assert mux.on_phase(NAVIGATING, 8, 0.1) is True


def test_fresh_mux_outputs_zero_before_any_phase():
    assert MotionMux(limits=LIMITS).decide(0.0).vx == 0.0


def test_unknown_phase_value_authorises_nothing():
    mux, t = armed(99)
    mux.on_nav(0.5, 0.5, t)
    mux.on_dock(0.5, 0.5, t)
    assert mux.decide(t).source is None
