from dataclasses import dataclass


TERMINAL = {'COMPLETED', 'CANCELED', 'REJECTED', 'FAILED', 'INTERRUPTED', 'TIMED_OUT'}

# 技术方案 §3.1.3 TaskSource plus VOICE from §3.12.2. An unlisted source is not
# a new kind of task, it is a bug or an impostor, so it is refused outright.
SOURCES = frozenset({'SCHEDULE', 'WEB', 'SYSTEM_BATTERY', 'VOICE'})

# 技术方案 §3.12.2. Arm work never goes through Nav2 and never moves the base.
ARM_TASKS = frozenset({'ARM_HOME', 'ARM_GRASP', 'ARM_RELEASE', 'ARM_STOP'})

# Tasks that may run while another task holds the arbiter. ARM_STOP is the only
# one: it is a request to stop, and a stop that has to queue behind the thing it
# is trying to stop is not a stop (技术方案 §3.12.2「语音『停止』」).
ALWAYS_ADMISSIBLE = frozenset({'ARM_STOP'})

# Ordinary tasks, whatever their source, never outrank manual takeover, the
# e-stop, a safety fault or a critical recharge.
PREEMPTIBLE_SOURCES = frozenset({'SCHEDULE', 'WEB', 'VOICE'})


@dataclass
class TaskState:
    task_id: str
    # Carried so the arbiter can tell a critical recharge from an ordinary task
    # without reaching back into the goal it came from.
    source: str = ''
    status: str = 'ACCEPTED'
    stage: str = 'PRECHECK'
    progress: float = 0.0
    message: str = 'task accepted'
    result_code: str = ''
    interruption_reason: str = ''

    def transition(self, status, stage, message, progress=None, code='', reason=''):
        if self.status in TERMINAL:
            raise ValueError('terminal tasks cannot transition')
        self.status, self.stage, self.message = status, stage, message
        if progress is not None:
            self.progress = float(progress)
        self.result_code, self.interruption_reason = code, reason


def is_arm_task(task_type: str) -> bool:
    return task_type in ARM_TASKS


def admission_reason(source: str, task_type: str, busy: bool,
                     battery_recharging: bool = False) -> str:
    """Why this goal may not be accepted, or '' if it may.

    Applied before any precheck: it decides whether the request is even the kind
    of thing this node accepts, which is cheaper and clearer than discovering it
    halfway through execution.
    """
    if source not in SOURCES:
        return 'UNKNOWN_SOURCE'
    if task_type in ALWAYS_ADMISSIBLE:
        return ''
    if busy:
        return 'TASK_BUSY'
    if battery_recharging and source in PREEMPTIBLE_SOURCES:
        # A critical recharge is the one task that must not be pushed aside.
        return 'BATTERY_RECHARGE_ACTIVE'
    return ''


def arm_precheck_reason(status_fresh, robot_status, arm_ready, base_stopped):
    """Arm tasks need a settled chassis, not a navigable one.

    Deliberately not reusing precheck_reason: that one requires Nav2 and valid
    localisation, neither of which an arm task uses. Reusing it would refuse a
    perfectly safe grasp just because no map is loaded.
    """
    if not status_fresh or robot_status is None or not robot_status.stm32_link_ok:
        return 'STM32_STATUS_UNAVAILABLE'
    if robot_status.remote_override:
        return 'REMOTE_OVERRIDE'
    if not robot_status.watchdog_healthy:
        return 'WATCHDOG_UNHEALTHY'
    if not robot_status.safety_permit or robot_status.fault_code:
        return 'SAFETY_NOT_PERMITTED'
    if not base_stopped:
        return 'BASE_NOT_STOPPED'
    if not arm_ready:
        return 'ARM_UNAVAILABLE'
    return ''


def precheck_reason(status_fresh, odom_fresh, robot_status, navigation_ready):
    if not status_fresh or robot_status is None or not robot_status.stm32_link_ok:
        return 'STM32_STATUS_UNAVAILABLE'
    if robot_status.remote_override:
        return 'REMOTE_OVERRIDE'
    if not robot_status.command_fresh:
        return 'COMMAND_NOT_FRESH'
    if not robot_status.watchdog_healthy:
        return 'WATCHDOG_UNHEALTHY'
    if not robot_status.safety_permit or robot_status.fault_code:
        return 'SAFETY_NOT_PERMITTED'
    if not robot_status.wheel_odom_valid or not robot_status.imu_valid or not odom_fresh:
        return 'LOCALIZATION_INPUT_UNAVAILABLE'
    if not navigation_ready:
        return 'NAVIGATION_UNAVAILABLE'
    return ''
