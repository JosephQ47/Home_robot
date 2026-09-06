"""Minimal Linux UART wrapper for the STM32 USB serial link."""
import array
import fcntl
import os
import termios


_BAUD = {115200: termios.B115200, 230400: termios.B230400,
         460800: termios.B460800, 921600: termios.B921600}


class SerialPort:
    def __init__(self, path: str, baud: int):
        if baud not in _BAUD:
            raise ValueError(f"unsupported baud: {baud}")
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = attrs[1] = attrs[3] = 0
        attrs[2] = termios.CS8 | termios.CLOCAL | termios.CREAD
        attrs[4] = attrs[5] = _BAUD[baud]
        attrs[6][termios.VMIN] = attrs[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        termios.tcflush(self.fd, termios.TCIFLUSH)

    @property
    def in_waiting(self):
        value = array.array('i', [0])
        fcntl.ioctl(self.fd, termios.FIONREAD, value, True)
        return value[0]

    def read(self, size):
        try:
            return os.read(self.fd, size)
        except BlockingIOError:
            return b''

    def write(self, data):
        return os.write(self.fd, data)

    def close(self):
        if self.fd is not None:
            os.close(self.fd); self.fd = None
