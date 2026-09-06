# Hi3516 应用开发准备

## 2026-09-05 资料核验

`/home/luckfox/Hi3516/packages/ReleaseDoc.zip` 已通过 ZIP CRC 检查。选择性提取的文档在 `/home/luckfox/Hi3516/docs`。

`/home/luckfox/Hi3516/packages/hi3516cv610_1020_musl.tar` 已完成归档扫描和解压。归档为普通 TAR，展开到 `/home/luckfox/Hi3516/sdk`，主 SDK 目录为 `/home/luckfox/Hi3516/sdk/Hi3516CV610_SDK_V1.0.2.0`。解压后 SDK 占用约 7.7 GB，根分区剩余约 2.7 GB，不适合继续全量展开嵌套源码包或做完整固件构建。

VMware Shared Folders 已挂载到 `/mnt/hgfs`，共享名为 `Hi3516_Linux`。`/mnt/hgfs/Hi3516_Linux/SMP_Linux_GCC_musl.rar` 中包含工具链、PQTools、AQTools、board SDK tgz 和参考包。本轮只提取了工具链成员 `gcc-20250305-arm-v01c02-linux-musleabi.tgz`，没有重复展开 RAR 中的 SDK/参考包。

《Hi35xxVxxx 开发环境用户指南》文档版本 01（2025-03-19）确认：

- 发布构建环境为 Ubuntu 22.04 LTS，推荐 64 位服务器。
- 文档指定工具链前缀 `arm-v01c02-linux-musleabi-`，表中交叉 GCC 为 10.3.0、musl 为 1.2.3。实际配套工具链版本及与板上固件的一致性仍需源码包核对。
- 完整开发服务器推荐内存 >=16 GB、硬盘 >=600 GB；这不是最小应用的实测最低要求。现有虚拟机约 4 GB 内存，本轮不编译完整固件。

工具链已展开到 `/home/luckfox/Hi3516/toolchain/gcc-20250305-arm-v01c02-linux-musleabi/arm-v01c02-linux-musleabi-gcc`。实际可执行名前缀为 `arm-linux-musleabi-`。`arm-linux-musleabi-gcc -v` 输出版本为 GCC 10.3.0，pkgversion 包含 `musl-1.2.3 linux-5.10 CS71.2.10.5.B002 2025-03-05 12:00:00`。

《Hi3516CV610 Sensor support list》版本 01（2025-04-15）列出 SC4336p 的 2560×1440@30 与 1920×1080@30，MIPI、linear、10 bit，FPS 栏为 2.5–30。1440p 的 Function/PQ 状态均 DONE；1080p 为 Function DONE、PQ NA。这是原厂支持表，不等于当前幽燕 PQ 配置已经支持任意切换。

## 最小应用

`hello/main.c` 仅打印成功标识、内核版本和架构，不操作相机、网络或底盘。Makefile 要求显式指定交叉编译器，不会静默使用 PC gcc。

SDK 的 `smp/a7_linux/source/cfg.mak` 确认当前配置为 Hi3516CV610、Linux 5.10、32 位 ARM、musl，配置中的交叉前缀为 `arm-v01c02-linux-musleabi-`。实际工具链命令使用 `arm-linux-musleabi-` 前缀，在 `hello` 中执行：

```bash
make CROSS_COMPILE=/home/luckfox/Hi3516/toolchain/gcc-20250305-arm-v01c02-linux-musleabi/arm-v01c02-linux-musleabi-gcc/bin/arm-linux-musleabi-
```

产物为 `build/hello_hi3516`，同时生成 ELF 头/解释器/ARM 属性报告和 SHA256。此命令中的目录是占位符，不是已找到的路径。

部署前对照板上 ARM 架构、musl 动态加载器及现有程序 ABI 核对 ELF。传输路径必须先验证可达、挂载类型和可用空间；不默认存在 SCP/NFS，不将录像写入 NAND，不把 `/tmp` 默认视为内存盘。本次板上挂载表没有单独的 `/tmp` tmpfs。

已完成交叉编译，产物为 `hello/build/hello_hi3516`。ELF 为 32 位 ARM，解释器 `/lib/ld-musl-arm.so.1`，SHA256 为 `e69c6a99cadaf9a6ea62c147c28a8f4ddd0d8c8ea6268858062f934602719f10`。

已通过串口把 hello 部署到板上 `/run/hello_hi3516`，校验值一致，执行输出 `HI3516_APP_CHECK_OK`、`kernel=5.10.221`、`architecture=armv7l`，退出码 0。`/run` 是 tmpfs，小测试程序不会写 NAND。

已通过 PC gcc 的纯语法检查（不生成产物），并验证未指定工具链时 Makefile 会拒绝构建；最终验收以板上执行通过为准。

## 网络与视频现状

- CH344 D 通道为海思 root shell，115200、8N1。
- 新 WiFi 已认证并通过 DHCP 取得地址，最近读到 `192.168.0.112/24`，网关 `192.168.0.1`；地址每次重新确认。
- 虚拟机访问该地址的 TCP 554/22/23 均超时，不能假定这些服务已开启。等待 Windows 对照测试以定位网络链路。
- 本轮采用 RTSP 调试路径；已准备 Ubuntu ROS 图像输入及 CPU YOLO，见 `../upper/README-vision.md`。
- 板上视频尚未重新启动，低负载编码参数尚待配置定义核验。未进行刷写、USB 角色切换或底盘控制。

## 摄像头 Sample 线索

SDK 中已有预编译 ARM/musl 版本 `smp/a7_linux/source/mpp/sample/venc/sample_venc` 和 `overlay/youyan/sample/sample_venc`。`file` 显示它们都是 32 位 ARM EABI5、动态链接、解释器 `/lib/ld-musl-arm.so.1`，与板上 musl 环境方向一致。

`smp/a7_linux/source/mpp/sample/Makefile.param` 默认 `SENSOR0_TYPE` 和 `SENSOR1_TYPE` 均为 `SC4336P_MIPI_4M_30FPS_10BIT`，`BOARD_TYPE` 为 `DMEB_QFN`，并启用了 `__RTSP__` 编译宏。`sample/venc/sample_venc.c` 中带 RTSP 逻辑，启用参数会创建 554 端口，路径包含 `/live.h264` 和 `/live.h265`。这与板上 PQ 工具的 `rtsp://<ip>:554/0` 不是同一个入口，后续验证时要分别记录。

已找到 SC4336P 相关 PQ 配置：`overlay/system/Hi3516CV610_PQ_V1.0.2.0/configs/sc4336p/`，包含 4M30、2M30、3M30、4M15 双路等配置文件。修改低负载档位前必须先备份原文件，并确认实际程序读取的是哪个配置。

已使用工具链重新编译 `smp/a7_linux/source/mpp/sample/venc`，命令为：

```bash
make CROSS=/home/luckfox/Hi3516/toolchain/gcc-20250305-arm-v01c02-linux-musleabi/arm-v01c02-linux-musleabi-gcc/bin/arm-linux-musleabi- \
     CROSS_COMPILE=/home/luckfox/Hi3516/toolchain/gcc-20250305-arm-v01c02-linux-musleabi/arm-v01c02-linux-musleabi-gcc/bin/arm-linux-musleabi-
```

编译成功，厂商源码存在 warning，但未失败。新产物与预编译产物同为 32 位 ARM/musl PIE，动态依赖 `libstdc++.so.6` 和 `libc.so`。串口 heredoc/base64 传输 1.2 MB 级样例不稳定，后续大文件部署应改用 TFTP、Telnet/FTP、SD 卡或桥接网络。

## UVC YUYV/YUY2 640×480@30 测试包

目标是让 Hi3516 通过 USB Device 口枚举为 UVC 摄像头，PC 直接接收 YUYV/YUY2 640×480@30。YUYV 640×480@30 原始带宽约为 640×480×2×30 = 18.4 MB/s，约 147 Mbps，理论上适合 USB2 High-Speed，但会明显高于 H.265 RTSP 的网络码率；优点是低延迟、无压缩马赛克，更适合先喂给 YOLO。

已编译测试包：

```text
Home_robot/hi3516/build/uvc_yuyv_640x480/sample_uvc
Home_robot/hi3516/build/uvc_yuyv_640x480/sample_uvc_v4l2
Home_robot/hi3516/build/uvc_yuyv_640x480/SHA256SUMS
```

对应源码补丁：

```text
Home_robot/hi3516/patches/uvc_yuyv_640x480_sample.patch
```

部署到板上前先确认：

1. 串口 shell 已恢复，不再停留在 heredoc 的 `>` 续行状态。
2. 板端存在 `/dev/uvc*` 或 UVC 驱动节点，且 `ot_uvc.ko`/媒体驱动已加载。
3. 找到板端或发布包中的 `ConfigUVC.sh`，并把它的 YUYV 640×480@30 descriptor 与 `uvc.h` 的 YUYV 帧表顺序保持一致。
4. 用 SD 卡、TFTP 或稳定网络传输 1.3MB 产物，不再用串口 heredoc 传大文件。

初次板上运行建议放在 `/run` 或 SD 卡临时目录，命令形态按官方 sample 为：

```bash
./sample_uvc 1 0
```

其中 `1` 是一个 UVC 设备，`0` 是 MPP 绑定到 UVC。若 PC 端选择 YUYV 这种非编码格式，程序内部会切到 YUV frame 路径。PC 端先用 Windows 相机/OBS/VLC 或 Ubuntu `v4l2-ctl --list-formats-ext` 验证枚举，再把设备接入 YOLO/ROS。

## 板端 USB 角色检查结果

2026-09-05 实测板端 `/dev/uvc`、`ot_uvc`、`usb_f_uvc` 存在，`configfs` 可挂载；但 `/sys/class/udc` 为空，extcon 为 `USB=0`、`USB-HOST=1`。Type-C 接到 PC 后状态未变化，虚拟机 `lsusb` 只看到 CH344 串口，没有新增 Hi3516 UVC/USB 设备。设备树 DWC3 为 `dr_mode=otg`、`maximum-speed=high-speed`。用户确认该板外露 Type-C 是 Host 口，因此 PC 不能枚举它符合板级接口现状。

UVC gadget 输出要求 PC 是 Host、Hi3516 是 Device。当前板子外露口按 Host 使用，不能直接作为 UVC 摄像头接 PC。除非厂商资料确认有 Device/OTG 切换方法、隐藏接口或对应固件，否则该路径暂停，改回 RTSP 视频输出链路。若以后拿到可切换方案，再先检查：

```bash
cat /sys/devices/platform/10300000.usb20drd/extcon/extcon0/state
ls -la /sys/class/udc
```

期望看到 `USB=1`、`USB-HOST=0`，并且 `/sys/class/udc` 下出现 UDC 节点。只有这一步成立，后续 `ConfigUVC.sh` 才能把 gadget 绑定起来。当前板级 Host 口不满足这个前提。

## UVC 配置与 Hi3516 YOLO 判断（2026-09-05）

UVC 不是单独运行 `sample_uvc` 就能让 PC 看到摄像头，它至少需要两层同时匹配：

1. USB gadget/configfs 描述符：在板端 `/sys/kernel/config/usb_gadget` 下创建 UVC function，声明格式、分辨率、帧间隔、buffer size、USB 包大小，并绑定到 `/sys/class/udc` 下的 UDC。
2. UVC 供帧应用：`sample_uvc`/`sample_uvc_v4l2` 从 VI/VPSS 取图并按描述符声明的格式送到 `/dev/uvc`。

已按本地 SDK 文档要求准备了 YUYV/YUY2 640×480@30 的两部分材料：

- gadget 脚本草案：`Home_robot/hi3516/uvc/ConfigUVC_yuyv_640x480.sh`
- sample 补丁：`Home_robot/hi3516/patches/uvc_yuyv_640x480_sample.patch`
- 已编译产物：`Home_robot/hi3516/build/uvc_yuyv_640x480/sample_uvc`、`sample_uvc_v4l2`

640×480 YUYV 每帧 614400 字节，30fps 原始数据约 18.4 MB/s，约 147 Mbps。按 SDK 文档中的计算方式，30fps 帧间隔为 `333333`，若按 25ms 传输窗口估算，High-Speed `streaming_maxpacket/xfersize` 使用 `3072`。

当前板端实测 `/sys/class/udc` 为空，extcon 为 `USB=0`、`USB-HOST=1`，用户也确认外露 Type-C 是 Host 口。因此 PC 识别不到 UVC 设备是板级 USB 角色导致的正常结果。`ConfigUVC_yuyv_640x480.sh` 现在只作为可审查脚本保留；在没有 UDC 节点之前运行会主动失败，不会完成 UVC 绑定。若厂家提供 Device/OTG 切换方法、隐藏 Device 接口或对应固件，再继续实测。

Hi3516CV610 可以跑厂商形态的 YOLO，不等于可以像 PC/RK3588 那样直接运行 Ultralytics/PyTorch。SDK 中已找到 SVP_NPU YOLOv8 sample 和 `.om` 模型：

- `Home_robot/hi3516/build/svp_npu_yolo/sample_svp_npu_main`
- `Home_robot/hi3516/build/svp_npu_yolo/yolov8.om`
- `Home_robot/hi3516/build/svp_npu_yolo/svp_npu_readme.txt`

SDK sample 的链路是 `VI -> VPSS -> SVP_NPU -> VGS -> VENC`，运行方式以 sample readme/源码为准，常见形态为 `./sample_svp_npu_main a 8`，带 RTSP 参数时还需继续按源码确认第三个参数。用户提供的厂商资料截图称 YOLOv8 只支持 20S，且 aidetect 与 yolov8 同时只能运行一个；这目前记录为厂商资料说法，尚未板端实测。

工程建议：当前机器人调试优先保持 Hi3516 负责采集、ISP、编码、RTSP，PC/Windows 或 Ubuntu 负责 YOLO/ROS。板端 YOLO 可以作为后续边缘检测/叠框/降算力方向验证，但要按 `.om` 模型、SVP ACL/NPU C/C++ sample 路径走，不能按普通 Python YOLO 路径规划。

## AI component aidetect 初步定位（2026-09-05）

`aidetect` 是海思/SDK AI component 的检测接口和示例，不是 PC 侧 Ultralytics YOLO，也不是本轮 RTSP + PC YOLO 的必要组件。

SDK 中存在两类相关 sample：

- `svp/ai_component/aidetect/sample_aidetect`：离线 YUV 图片检测。输入为 YUV 文件、`.bin` 检测模型和图像尺寸；文档建议内存紧张时用 `-v` 从路径加载模型以降低峰值。
- `svp/ai_component/aidetect_vie/sample_aidetect_vie` 与 `sample/kol`：实时视频链路中插入 AI 检测，典型路径为 `vi-vpss-aidetect-vgs-venc`，可将检测框交给 VGS/VENC 叠加输出。

它依赖 `libss_mpi_aidetect`、`ss_mpi_aidetect_*` API 和 SDK 自带 `.bin` 模型，例如 `det_hvf_hor.bin`、`det_pet_hor.bin` 等。它更适合验证厂商内置轻量检测/智能曝光/叠框能力；若目标是通用 COCO 类别或自训练 YOLO，优先仍走 PC/RK3588 侧 YOLO，或者走 SDK 的 SVP_NPU YOLOv8 `.om` sample。

## SoC 用户指南新增依据（2026-09-05）

已抽取 `/home/luckfox/d2lros2/Hi3516CV610 超高清智慧视觉 SoC 用户指南.pdf` 到 `Home_robot/hi3516/docs/Hi3516CV610_SoC_User_Guide.txt`。该文档是芯片用户指南，用于核对芯片能力，不代表当前幽燕开发板接口一定全部引出或当前固件已启用。

与当前任务相关的依据：

- 芯片特性列出 1 个 USB2.0 Host/Device 接口。
- USB DRD 章节说明芯片支持 1 个 USB2.0 DRD 接口，可工作在 USB2.0 Host 或 Device 模式，但不支持动态切换。
- Host 模式支持 480Mbps/12Mbps/1.5Mbps；Device 模式支持 480Mbps/12Mbps。
- NPU 章节说明 NPU 是面向 CNN、RCNN 等神经网络结构的专用加速器，可用于图片分类、目标检测等场景。

这进一步支持当前判断：Hi3516CV610 芯片有 USB Device/UVC gadget 的硬件基础，但当前开发板外露 Type-C 处于 Host 侧且 `/sys/class/udc` 为空，因此不能靠普通应用脚本在运行中动态切成 UVC 摄像头。若要继续 UVC，需要厂商确认板级 Device/OTG 接法、启动时角色配置或专用固件。

