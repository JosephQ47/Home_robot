"""Small bench tool for validating the real USB-UART link."""

from __future__ import annotations

import argparse
import time

from .serial_bridge import SerialBridge


class PySerialTransport:
    def __init__(self, port: str, baud: int) -> None:
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - depends on the bench PC
            raise SystemExit("请先安装 pyserial：python -m pip install pyserial") from exc
        self.serial = serial.Serial(port, baudrate=baud, timeout=0)

    def write(self, data: bytes) -> int:
        return self.serial.write(data)

    def read_available(self) -> bytes:
        return self.serial.read(self.serial.in_waiting or 1)

    def close(self) -> None:
        self.serial.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="HomeRobot STM32 X-Protocol bench tool")
    parser.add_argument("--port", required=True, help="例如 COM3 或 /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=230400)
    parser.add_argument("--vx", type=int, default=0, help="线速度 mm/s")
    parser.add_argument("--wz", type=int, default=0, help="角速度 mrad/s")
    parser.add_argument("--hz", type=float, default=10.0, help="速度帧发送频率")
    args = parser.parse_args()
    transport = PySerialTransport(args.port, args.baud)
    bridge = SerialBridge(transport)
    interval = 1.0 / args.hz
    print(f"连接 {args.port} @ {args.baud}，Ctrl-C 停止并发送零速")
    try:
        while True:
            bridge.send_velocity(args.vx, args.wz)
            for state in bridge.poll():
                print(
                    f"state velocity={state.velocity} accel={state.accel} "
                    f"gyro={state.gyro} battery={state.battery_x100 / 100:.2f}V"
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
        transport.close()


if __name__ == "__main__":
    main()
