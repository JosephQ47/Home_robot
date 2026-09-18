"""Maps ASR text to a whitelisted task request, or to a refusal.

Voice produces discrete task requests only. It never publishes velocity and
never drives a servo. Anything that is not an exact match against the frozen
command set and the accepted configuration is refused out loud rather than
guessed at.

# @spec 家庭服务机器人技术方案.md#3.12.2
"""
import re
from dataclasses import dataclass, field

# 技术方案 §3.12.2 的有限命令集。新增命令必须先改方案再改这里。
PATTERNS = (
    (re.compile(r'^开始巡检$'), 'patrol', ()),
    (re.compile(r'^去(?P<location>.+)$'), 'navigate', ('location',)),
    (re.compile(r'^搜索(?P<target_class>.+)$'), 'search', ('target_class',)),
    (re.compile(r'^抓取(?P<target_class>.+)$'), 'arm_grasp', ('target_class',)),
    (re.compile(r'^放到(?P<place>.+)$'), 'arm_release', ('place',)),
    (re.compile(r'^机械臂回零$'), 'arm_home', ()),
    (re.compile(r'^打开夹爪$'), 'gripper_open', ()),
    (re.compile(r'^关闭夹爪$'), 'gripper_close', ()),
    (re.compile(r'^停止$'), 'stop', ()),
    (re.compile(r'^回充$'), 'dock', ()),
    (re.compile(r'^报告电量$'), 'report_battery', ()),
)

# Refused regardless of what the user says, because voice is an ordinary task
# source and must not outrank manual takeover, the e-stop or a critical recharge.
BLOCKING_STATES = ('estop', 'remote_override', 'safety_fault', 'battery_critical')

# 'stop' asks to cancel the current task and halt the arm. It does not clear a
# latched fault and it is not a substitute for the hardware e-stop, so it is
# allowed through the blocking states above — but only as a cancel request.
ALWAYS_ALLOWED = ('stop',)


@dataclass(frozen=True)
class Intent:
    intent: str
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Refusal:
    reason: str
    spoken: str


@dataclass(frozen=True)
class Vocabulary:
    """What the accepted configuration actually contains."""
    locations: frozenset = frozenset()
    target_classes: frozenset = frozenset()
    places: frozenset = frozenset()


PARAM_VOCABULARY = {'location': 'locations', 'target_class': 'target_classes',
                    'place': 'places'}


def interpret(text: str, confidence: float, vocabulary: Vocabulary,
              min_confidence: float = 0.75, awake: bool = True,
              task_busy: bool = False, **states) -> Intent | Refusal:
    """Turn one ASR result into a task request or an explained refusal."""
    if not awake:
        # V-1: nothing is heard before the wake word.
        return Refusal('not_awake', '')
    text = (text or '').strip()
    if confidence < min_confidence:
        # V-3: a guess is worse than a question.
        return Refusal('low_confidence', '没听清，请再说一次')
    matched = None
    for pattern, intent, params in PATTERNS:
        hit = pattern.match(text)
        if hit:
            if matched is not None:
                return Refusal('ambiguous', '这句话有歧义，请换一种说法')
            matched = (intent, {name: hit.group(name) for name in params})
    if matched is None:
        # V-2: outside the whitelist entirely.
        return Refusal('unknown_command', '这个命令不支持')
    intent, params = matched
    for name, value in params.items():
        allowed = getattr(vocabulary, PARAM_VOCABULARY[name])
        if value not in allowed:
            # V-2: an unaccepted location or class is refused, never approximated.
            return Refusal(f'unknown_{name}', f'没有已验收的{value}')
    if intent not in ALWAYS_ALLOWED:
        for state in BLOCKING_STATES:
            if states.get(state):
                # V-4
                return Refusal(state, '当前状态不允许执行该任务')
        if task_busy:
            return Refusal('task_busy', '当前有任务正在执行')
    return Intent(intent, params)


def is_cancel_only(intent: Intent) -> bool:
    """V-5: 'stop' cancels; it never clears a latched fault."""
    return intent.intent == 'stop'
