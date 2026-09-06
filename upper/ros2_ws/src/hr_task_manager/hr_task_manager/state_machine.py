from dataclasses import dataclass


TERMINAL = {'COMPLETED', 'CANCELED', 'REJECTED', 'FAILED', 'INTERRUPTED', 'TIMED_OUT'}


@dataclass
class TaskState:
    task_id: str
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
