"""Small POSIX UART wrapper used to keep the radar node dependency-free."""
import array
import fcntl
import os
import termios


_BAUD = {
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
}


class SerialPort:
    def __init__(self, path: str, baud: int):
        if baud not in _BAUD:
            raise ValueError(f'unsupported baud rate: {baud}')
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        settings = termios.tcgetattr(self.fd)
        settings[0] = 0
        settings[1] = 0
        settings[2] = termios.CS8 | termios.CLOCAL | termios.CREAD
        settings[3] = 0
        settings[4] = _BAUD[baud]
        settings[5] = _BAUD[baud]
        settings[6][termios.VMIN] = 0
        settings[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, settings)
        termios.tcflush(self.fd, termios.TCIFLUSH)

    @property
    def in_waiting(self) -> int:
        value = array.array('i', [0])
        fcntl.ioctl(self.fd, termios.FIONREAD, value, True)
        return value[0]

    def read(self, size: int) -> bytes:
        try:
            return os.read(self.fd, size)
        except BlockingIOError:
            return b''

    def write(self, data: bytes) -> int:
        return os.write(self.fd, data)

    def flush(self):
        termios.tcdrain(self.fd)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
