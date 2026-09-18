"""Rules V-1..V-6 from docs/features/hr_voice.md."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_voice_command.intent import (BLOCKING_STATES, Intent, Refusal,  # noqa: E402
                                     Vocabulary, interpret, is_cancel_only)

VOCAB = Vocabulary(locations=frozenset({'客厅', '厨房'}),
                   target_classes=frozenset({'杯子', '人员'}),
                   places=frozenset({'桌面'}))


def say(text, **kw):
    kw.setdefault('confidence', 0.95)
    return interpret(text, kw.pop('confidence'), VOCAB, **kw)


def test_nothing_is_heard_before_the_wake_word():
    assert isinstance(say('开始巡检', awake=False), Refusal)


def test_whole_whitelist_is_accepted():
    for text, intent in (('开始巡检', 'patrol'), ('去客厅', 'navigate'),
                         ('搜索杯子', 'search'), ('抓取杯子', 'arm_grasp'),
                         ('放到桌面', 'arm_release'), ('机械臂回零', 'arm_home'),
                         ('打开夹爪', 'gripper_open'), ('关闭夹爪', 'gripper_close'),
                         ('停止', 'stop'), ('回充', 'dock'), ('报告电量', 'report_battery')):
        out = say(text)
        assert isinstance(out, Intent) and out.intent == intent, text


def test_command_outside_the_whitelist_is_refused():
    out = say('前进两米')
    assert isinstance(out, Refusal) and out.reason == 'unknown_command'


def test_low_confidence_asks_instead_of_guessing():
    out = say('去客厅', confidence=0.5)
    assert isinstance(out, Refusal) and out.reason == 'low_confidence'


def test_confidence_boundary():
    assert isinstance(say('去客厅', confidence=0.75), Intent)
    assert isinstance(say('去客厅', confidence=0.7499), Refusal)


def test_unaccepted_location_is_refused_not_approximated():
    out = say('去阳台')
    assert isinstance(out, Refusal) and out.reason == 'unknown_location'


def test_unaccepted_target_and_place_are_refused():
    assert say('搜索飞机').reason == 'unknown_target_class'
    assert say('抓取飞机').reason == 'unknown_target_class'
    assert say('放到天花板').reason == 'unknown_place'


def test_voice_never_outranks_safety():
    """V-4: every blocking state refuses every ordinary voice task."""
    for state in BLOCKING_STATES:
        for text in ('开始巡检', '去客厅', '抓取杯子', '回充'):
            out = say(text, **{state: True})
            assert isinstance(out, Refusal) and out.reason == state, (state, text)


def test_stop_is_still_accepted_under_blocking_states():
    for state in BLOCKING_STATES:
        out = say('停止', **{state: True})
        assert isinstance(out, Intent) and is_cancel_only(out)


def test_busy_refuses_new_tasks_but_not_stop():
    assert isinstance(say('去客厅', task_busy=True), Refusal)
    assert isinstance(say('停止', task_busy=True), Intent)


def test_empty_and_whitespace_input():
    assert isinstance(say(''), Refusal)
    assert isinstance(say('   '), Refusal)
    assert isinstance(interpret(None, 0.99, VOCAB), Refusal)


def test_refusals_carry_something_to_say_back():
    """V-3/V-6: the user is told why, and the reason is auditable."""
    for out in (say('前进两米'), say('去阳台'), say('去客厅', confidence=0.1)):
        assert out.reason and out.spoken
