#!/bin/sh
# Temporary Hi3516 UVC gadget descriptor for YUYV/YUY2 640x480@30.
# This script only configures USB configfs. It does not start media capture;
# run sample_uvc after this script succeeds.
# Precondition: the board USB controller must expose a UDC under /sys/class/udc.

set -eu

GADGET=${GADGET:-camera}
CONFIG_ROOT=/sys/kernel/config
G=$CONFIG_ROOT/usb_gadget/$GADGET
FUNC=uvc.usb0
CFG=c.1
UVC=$G/functions/$FUNC
FRAME=$UVC/streaming/uncompressed/yuyv/480p
UDC_NAME=${UDC_NAME:-}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

[ -d /sys/class/udc ] || fail "/sys/class/udc missing; USB Device Controller is not available"
if [ -z "$UDC_NAME" ]; then
    UDC_NAME=$(ls /sys/class/udc 2>/dev/null | head -n 1 || true)
fi
[ -n "$UDC_NAME" ] || fail "no UDC found; current USB role is probably Host, not Device"

if ! mount | grep -q " $CONFIG_ROOT type configfs "; then
    mount -t configfs none "$CONFIG_ROOT"
fi

# Clean any previous temporary gadget with the same name.
if [ -d "$G" ]; then
    if [ -f "$G/UDC" ]; then
        echo "" > "$G/UDC" 2>/dev/null || true
    fi
    rm -f "$G/configs/$CFG/$FUNC" 2>/dev/null || true
    rm -rf "$G" 2>/dev/null || fail "cannot remove previous gadget $G"
fi

mkdir -p "$G"
cd "$G"

# Linux Foundation sample VID/PID for local lab testing only.
echo 0x1d6b > idVendor
echo 0x0102 > idProduct
echo 0x0200 > bcdUSB
echo 0x0100 > bcdDevice

echo 0xEF > bDeviceClass
echo 0x02 > bDeviceSubClass
echo 0x01 > bDeviceProtocol

mkdir -p strings/0x409
echo "Hi3516CV610-lab" > strings/0x409/serialnumber
echo "YouYan" > strings/0x409/manufacturer
echo "Hi3516 YUY2 Camera" > strings/0x409/product

mkdir -p configs/$CFG/strings/0x409
echo 0x80 > configs/$CFG/bmAttributes
echo 250 > configs/$CFG/MaxPower
echo "UVC YUY2 640x480" > configs/$CFG/strings/0x409/configuration

mkdir -p functions/$FUNC

# High-speed is what the board device tree reports. 3072 is the documented HS maximum.
echo 3072 > functions/$FUNC/streaming_maxpacket
echo 1 > functions/$FUNC/streaming_interval

# UVC 1.00, 48 MHz clock.
mkdir -p functions/$FUNC/control/header/h
if [ -f functions/$FUNC/control/header/h/bcdUVC ]; then
    echo 0x0100 > functions/$FUNC/control/header/h/bcdUVC
fi
if [ -f functions/$FUNC/control/header/h/dwClockFrequency ]; then
    echo 48000000 > functions/$FUNC/control/header/h/dwClockFrequency
fi
ln -s ../../header/h functions/$FUNC/control/class/fs/h
ln -s ../../header/h functions/$FUNC/control/class/hs/h

# YUY2 GUID: 32595559-0000-0010-8000-00AA00389B71, written in configfs byte order.
mkdir -p functions/$FUNC/streaming/uncompressed/yuyv
printf 'YUY2\000\000\020\000\200\000\000\252\0008\233q' > functions/$FUNC/streaming/uncompressed/yuyv/guidFormat
echo 16 > functions/$FUNC/streaming/uncompressed/yuyv/bBitsPerPixel
echo 1 > functions/$FUNC/streaming/uncompressed/yuyv/bDefaultFrameIndex

mkdir -p "$FRAME"
echo 640 > "$FRAME/wWidth"
echo 480 > "$FRAME/wHeight"
echo 147456000 > "$FRAME/dwMinBitRate"
echo 147456000 > "$FRAME/dwMaxBitRate"
echo 614400 > "$FRAME/dwMaxVideoFrameBufferSize"
echo 333333 > "$FRAME/dwDefaultFrameInterval"
echo 333333 > "$FRAME/dwFrameInterval"

mkdir -p functions/$FUNC/streaming/header/h
cd functions/$FUNC/streaming/header/h
ln -s ../../uncompressed/yuyv yuyv
cd "$G"
ln -s ../../header/h functions/$FUNC/streaming/class/fs/h
ln -s ../../header/h functions/$FUNC/streaming/class/hs/h

ln -s ../../functions/$FUNC configs/$CFG/$FUNC

echo "$UDC_NAME" > UDC

echo "UVC gadget configured on UDC=$UDC_NAME"
echo "Run the media application next, e.g.: ./sample_uvc 1 0"
