# Home Robot 调试状态

更新时间：2026-09-05

## 当前结论

系统调试已经推进到“Hi3516 RTSP → PC ROS 图像 → CPU YOLO 已实测，ROS 2 全框架可构建，短程目标与目标跟随控制链已在安全 Mock 环境端到端通过，下位机旧协议只读接入已实测”的阶段。UVC sample 侧虽已准备，但当前板级 Type-C 为 Host，不能作为现阶段视频主链。

正式技术方案仍以 RK3588 为上位机；本轮 PC 临时代替 RK3588。当前未启动底盘运动，未刷写固件，未修改启动分区。

## 已完成

- Hi3516CV610 板卡已通过串口进入 root shell。CH344 D 通道对应海思调试口，虚拟机中曾识别为 `/dev/ttyACM3`，串口参数 115200 8N1。
- 板上官方 PQ 程序曾跑通 SC4336P 摄像头、ISP、编码、RTSP 服务，Windows VLC 曾播放 `rtsp://<board-ip>:554/0`。
- 已确认板上实际 PQ 目录为 `/system/Hi3516CV610_PQ_V1.0.2.0`，不是文档中的连字符路径。
- WiFi 已配置过新 SSID，并通过 DHCP 获得过 `192.168.0.112/24`。该地址需每次重新确认。
- Ubuntu 虚拟机内已准备 CPU 视觉链路：ROS 2 图像源节点、YOLO 感知节点、本地图片/视频/模拟源测试、launch 文件和说明。
- ReleaseDoc 文档已提取并检查，开发环境文档确认 Ubuntu 22.04、`arm-v01c02-linux-musleabi-`、GCC 10.3.0、musl 1.2.3。
- Hi3516 主 SDK 已解压到 `/home/luckfox/Hi3516/sdk/Hi3516CV610_SDK_V1.0.2.0`。
- SDK 配置确认目标为 Hi3516CV610、Linux 5.10、32 位 ARM、musl。
- SDK 中已找到 `sample_venc` 源码、预编译 ARM/musl 产物、SC4336P sensor 库和 PQ 配置。
- VMware Shared Folders 曾挂载到 `/mnt/hgfs/Hi3516_Linux`；最近一次检查 `/mnt/hgfs` 为空，若需要继续从 Windows 取资料需重新启用共享。
- 已从 `/mnt/hgfs/Hi3516_Linux/SMP_Linux_GCC_musl.rar` 中只提取 `gcc-20250305-arm-v01c02-linux-musleabi.tgz`，未重复提取 RAR 中的 SDK/参考包。
- 工具链已展开到 `/home/luckfox/Hi3516/toolchain/gcc-20250305-arm-v01c02-linux-musleabi/arm-v01c02-linux-musleabi-gcc`。实际命令前缀为 `arm-linux-musleabi-`，GCC 输出版本为 10.3.0，pkgversion 包含 `musl-1.2.3 linux-5.10 CS71.2.10.5.B002 2025-03-05 12:00:00`。
- `Home_robot/hi3516/hello` 已完成真实交叉编译，并通过串口部署到板上 `/run/hello_hi3516` 执行。板上输出 `HI3516_APP_CHECK_OK`，内核 `5.10.221`，架构 `armv7l`，退出码 0。
- SDK `sample/mpp/venc` 已用工具链重新编译成功。新产物为 32 位 ARM EABI5、解释器 `/lib/ld-musl-arm.so.1`，依赖 `libstdc++.so.6` 和 `libc.so`。

## 当前缺口

- 当前虚拟机没有枚举到海思调试串口 `/dev/ttyACM*` 或 `/dev/ttyUSB*`；要继续板端实测需重新把 CH344 D/COM9 接入虚拟机。
- 虚拟机到板子 WiFi 地址的 TCP 554/22/23 曾超时，不能假定 SSH/SFTP/Telnet 可用。
- 小文件可通过串口 base64 部署；1.2 MB 级 `sample_venc` 采用 heredoc/base64 串口传输不稳定，板端 shell 可能停留在多行输入状态。该尝试只写 `/run` tmpfs，未改 NAND。恢复后应改用 TFTP、Telnet/FTP、SD 卡或让虚拟机与板子进入同一二层网络。
- UVC 文档和 sample 已检查，SDK 支持 YUYV/YUY2；已准备 YUYV 640×480@30 的 sample 侧补丁并编译通过。实际 USB UVC 枚举仍未验证，且当前 SDK/共享目录内未找到 `ConfigUVC.sh`。

## UVC YUYV 640×480@30 准备状态

目标链路为 Hi3516CV610 作为 USB Device/UVC 摄像头，PC 作为 Host 接收 YUYV/YUY2 640×480@30，再进入 YOLO/ROS 视觉链路。该路径只验证视频输出，不启动底盘，不刷写固件，不修改启动分区。

本地 SDK 文档确认 UVC 支持 YUYV、NV12、NV21、MJPEG、H.264、H.265。文档要求新增或调整分辨率时同步修改 `ConfigUVC.sh` 和 `sample/uvc_app/uvc.h`，两者格式顺序与分辨率顺序必须一致，否则可能导致预览异常甚至内核崩溃。

已在 SDK sample 目录中准备应用侧改动：

- `uvc_app/uvc.h`：在 YUYV 帧表中新增并置顶 640×480@30，`dwFrameInterval=333333`，`ss_xfersize=9216`，`hs_xfersize=3072`。640×480 YUYV 单帧为 614400 bytes，按文档公式估算 30 fps 约需 3072 bytes/125us。
- `uvc_app/uvc_media.c`、`uvc_app/uvc_media_v4l2.c`：双 UVC/小 YUYV VB 池从 640×360 调整为 640×480。
- `uvc_app/camera.c`：默认关闭 UAC，并在 UAC 关闭时不创建/等待音频线程，降低纯视频测试负载。

原始文件已保存在 SDK 目录同名 `.orig_before_yuyv640x480` 备份。补丁归档在 `Home_robot/hi3516/patches/uvc_yuyv_640x480_sample.patch`。

构建命令：

```bash
cd /home/luckfox/Hi3516/sdk/Hi3516CV610_SDK_V1.0.2.0/smp/a7_linux/source/mpp/sample/uvc_app
make clean CROSS=/home/luckfox/Hi3516/toolchain/gcc-20250305-arm-v01c02-linux-musleabi/arm-v01c02-linux-musleabi-gcc/bin/arm-linux-musleabi- \
  CROSS_COMPILE=/home/luckfox/Hi3516/toolchain/gcc-20250305-arm-v01c02-linux-musleabi/arm-v01c02-linux-musleabi-gcc/bin/arm-linux-musleabi-
make CROSS=/home/luckfox/Hi3516/toolchain/gcc-20250305-arm-v01c02-linux-musleabi/arm-v01c02-linux-musleabi-gcc/bin/arm-linux-musleabi- \
  CROSS_COMPILE=/home/luckfox/Hi3516/toolchain/gcc-20250305-arm-v01c02-linux-musleabi/arm-v01c02-linux-musleabi-gcc/bin/arm-linux-musleabi-
```

构建产物已复制到 `Home_robot/hi3516/build/uvc_yuyv_640x480/`：

- `sample_uvc`：SHA256 `ece11d940836ac49a6a383394130c97a4eac867de89d0773cfe59a3150d81a9d`
- `sample_uvc_v4l2`：SHA256 `0939837f44fa3109ff006d4edccd6ebd7cc278ff7e0c0f97b3a6c9be57b3ab97`

两个产物均为 32 位 ARM EABI5、musl 动态链接、解释器 `/lib/ld-musl-arm.so.1`。

当前缺口：`ConfigUVC.sh` 未在已解压 SDK、文档目录或当前 VMware 共享目录中找到。后续必须从板端或完整发布包中找到/补齐该脚本，并把它的 YUYV 分辨率导出顺序改成与 `uvc.h` 一致，例如把 640×480 放在 YUYV 第一项。没有这个脚本，PC 端不会按预期枚举出 YUY2 640×480@30。

## 板端 UVC/USB 实测补充

2026-09-05 通过 CH344 D 通道 `/dev/ttyACM3` 重新接入板端 root shell，只读检查后得到：

- `/dev/uvc` 存在，`ot_uvc`、`usb_f_uvc`、`configfs` 相关内核能力存在。
- 手动挂载 `configfs` 后 `/sys/kernel/config/usb_gadget` 出现，但目录为空。
- `/sys/class/udc` 为空，当前没有可绑定的 USB Device Controller。
- dmesg 显示 `xhci-hcd` 主机控制器、`Host supports USB 3.0 SuperSpeed`，当前 USB 处于 Host 侧。设备树 DWC3 节点为 `dr_mode=otg`、`maximum-speed=high-speed`，说明固件描述为 OTG/USB2 High-Speed，不是应用层固定成 UVC Device。
- extcon 状态为 `USB=0`、`USB-HOST=1`。`/sys/class/usb_role/10300000.dwc3-role-switch` 存在，但没有可写 `role` 文件；当前未找到安全的运行时软件切换入口。
- 板端未找到 `ConfigUVC.sh`、`sample_uvc*` 或其他 UVC/gadget 启动脚本。

检查 `/sys` 时曾触发一次 OOM，系统杀掉 `wpa_supplicant`；已重新执行 `/system/wifi/wifi_start.sh RTL8189FS` 恢复 WiFi，DHCP 地址回到 `192.168.0.106`。后续避免在该板 32 MB Linux 内存下执行大范围 `find /sys`。

当前判断：用户确认板子外露 Type-C 为 Host 口，PC 不能枚举它是符合预期的。SDK/SoC 文档中的 UVC gadget 能力不等于当前幽燕开发板外露接口已经提供 USB Device 连接。除非厂商资料确认还有可用 Device/OTG 接口、跳线/拨码可切换，或允许更换固件/设备树/硬件连接，否则本板不能按“Hi3516 作为 UVC 摄像头接 PC”的路径继续。`sample_uvc` 构建产物保留为资料和后续板型/固件核验用。

## 下一步

1. 恢复板端串口 shell。若持续显示 `>` 续行提示，可重启/复位开发板；本次临时文件只在 `/run`，重启会自动消失。
2. 暂停 UVC gadget 实测路径；除非厂商资料确认有 Device/OTG 切换方法，否则不要继续尝试让 PC 枚举当前 Host 口。
3. 回到已验证的视频路径：Hi3516 负责 SC4336P 采集、ISP、编码和 RTSP 输出，PC/Windows 或 Ubuntu 接 RTSP 做 YOLO。
4. 建立稳定的大文件部署方式。优先使用 SD 卡、TFTP、HTTP 拉取或同网段网络；不要再用串口 heredoc 传 1MB 以上文件。
5. 继续验证低负载 RTSP 档位，例如 640×360/720p、较低码率和帧率，记录内存、码率、延迟、断流和画质。
6. 若后续必须走未压缩低延迟链路，再向厂商索要该板 USB Device/UVC 连接方式、原厂 `ConfigUVC.sh`、设备树/固件说明，或换带 Device 口的板型。

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

## RTSP + YOLO 实测脚本（2026-09-05）

已新增 `Home_robot/upper/tools/rtsp_yolo_check.py`，用于只启动 PC 侧视觉链路并统计结果。它启动 `hr_image_source` 和 `hr_perception`，订阅 `/camera/image_raw`、`/detections`、`/diagnostics`，不会启动串口桥、导航或速度话题。

离线图片自测命令：

```bash
cd /home/luckfox/d2lros2
source Home_robot/upper/vision_env.sh
cd Home_robot/upper/ros2_ws
python ../tools/rtsp_yolo_check.py   --source /home/luckfox/Hi3516/vision-assets/bus.jpg   --model /home/luckfox/Hi3516/vision-assets/yolov8n.pt   --duration 20   --require-detection   --target-class person
```

实测结果：通过。20 秒窗口内收到 26 条图像、6 条检测消息，`person` 命中 12 次，最新 CPU 推理约 162.5 ms，未出现 `/cmd_vel` 或 `/cmd_vel_auto`。

RTSP 实拍验收命令模板：

```bash
cd /home/luckfox/d2lros2
source Home_robot/upper/vision_env.sh
cd Home_robot/upper/ros2_ws
python ../tools/rtsp_yolo_check.py   --source rtsp://<当前板子IP>:554/0   --model /home/luckfox/Hi3516/vision-assets/yolov8n.pt   --duration 60   --require-detection   --target-class person   --publish-hz 8   --inference-hz 2   --image-size 320   --output-width 640   --log-dir /tmp/hr-rtsp-yolo-live
```

当前虚拟机网卡为 `192.168.164.129/24`，对之前记录的 `192.168.0.106` 和 `172.20.10.2` 均无法连通 TCP 554。CH344 串口已枚举为 `/dev/ttyACM0..3`，但当前用户缺少 `/dev/ttyACM3` 读写权限，因此暂时不能由 Codex 接管串口确认板端 IP/启动 RTSP。

## SoC 用户指南新增依据（2026-09-05）

已抽取 `/home/luckfox/d2lros2/Hi3516CV610 超高清智慧视觉 SoC 用户指南.pdf` 到 `Home_robot/hi3516/docs/Hi3516CV610_SoC_User_Guide.txt`。该文档是芯片用户指南，用于核对芯片能力，不代表当前幽燕开发板接口一定全部引出或当前固件已启用。

与当前任务相关的依据：

- 芯片特性列出 1 个 USB2.0 Host/Device 接口。
- USB DRD 章节说明芯片支持 1 个 USB2.0 DRD 接口，可工作在 USB2.0 Host 或 Device 模式，但不支持动态切换。
- Host 模式支持 480Mbps/12Mbps/1.5Mbps；Device 模式支持 480Mbps/12Mbps。
- NPU 章节说明 NPU 是面向 CNN、RCNN 等神经网络结构的专用加速器，可用于图片分类、目标检测等场景。

这进一步支持当前判断：Hi3516CV610 芯片有 USB Device/UVC gadget 的硬件基础，但当前开发板外露 Type-C 处于 Host 侧且 `/sys/class/udc` 为空，因此不能靠普通应用脚本在运行中动态切成 UVC 摄像头。若要继续 UVC，需要厂商确认板级 Device/OTG 接法、启动时角色配置或专用固件。

## RTSP 实拍 YOLO 验证结果（2026-09-05）

板端通过串口确认：

- 当前 WiFi 地址：`192.168.0.106/24`，默认路由 `192.168.0.1`。
- RTSP 启动命令：`cd /system/Hi3516CV610_PQ_V1.0.2.0 && ./PQTools.sh -s sc4336p >/tmp/pq_rtsp.log 2>&1 &`
- RTSP 监听：`0.0.0.0:554`，进程 `ittb_stream`。
- 当前默认码流仍为 `2560x1440 @ 30fps, H.265, bit_rate=6144`。
- RTSP 启动后板端 `free` 显示 available 约 3.8MB，内存余量很小。

PC/Ubuntu 实测：

1. 离线 YOLO/ROS 自测通过：20 秒内收到 26 条图像、6 条检测消息，`person` 命中 12 次。
2. RTSP 默认低负载验收参数 `output_width=640, imgsz=320, conf=0.35`：链路通，60 秒内收到 237 张图像、71 条检测消息，但当前画面未命中 `person`。
3. 抓取实拍帧 `Home_robot/upper/captures/hi3516_rtsp_latest.jpg`，原始尺寸 `2560x1440`。直接对该帧跑 YOLO，检测到 `person`，置信度约 `0.474`，说明图像内容在高分辨率下可被 YOLO 识别。
4. RTSP 调参验收 `output_width=1280, imgsz=640, conf=0.25, inference_hz=1`：通过。47.65 秒内收到 8 张 ROS 图像、8 条检测消息，`person` 命中 1 次，最新推理约 434.6 ms，未出现 `/cmd_vel` 或 `/cmd_vel_auto`。
5. 折中档 `output_width=640, imgsz=640, conf=0.25`：链路通，37.22 秒内收到 83 张图像、21 条检测消息，但未命中 `person`。原因倾向于当前画面是近距离手臂/局部人体，占满画面，缩小后不符合 COCO person 的典型形态。

结论：今天已验证“Hi3516 RTSP -> PC/Ubuntu ROS 图像 -> CPU YOLO -> /detections”链路可运行并能识别实拍画面中的 `person`。后续要做工程化参数，应让完整人体或目标物体处于画面中心，再在低负载码流/低分辨率下重新调阈值、输入尺寸和帧率。

## 低负载 RTSP 档位尝试（2026-09-05）

为降低默认 4MP 码流压力，已在板端应用目录内备份并切换 SC4336P PQ 模式：

- 原配置备份：`/system/Hi3516CV610_PQ_V1.0.2.0/configs/sc4336p/config_entry.ini.orig_20260905`
- 修改文件：`/system/Hi3516CV610_PQ_V1.0.2.0/configs/sc4336p/config_entry.ini`
- 修改值：`use_mode = 0` 改为 `use_mode = 5`
- 目标模式：`mode.5 = 2M30`，配置文件 `sc4336p_2M30.ini`

2M30 启动成功，日志确认：

- Sensor：`SC4336P_MIPI_27Minput_2lane_10bit_472.5Mbps_1920x1080_30fps Init OK`
- VENC：H.265，`pic_width=1920`，`pic_height=1080`，`src_frame_rate=30`，`dst_frame_rate=30`，`bit_rate=6144`
- RTSP：`0.0.0.0:554` listen 成功，`ittb_stream` 运行成功。

但随后板端 WiFi 数据面异常：板子保留 `192.168.0.106/24` 和默认路由 `192.168.0.1`，`wlan0` link 显示 100，ARP 表能看到网关/宿主机，但板子 ping 网关和宿主机均 100% 丢包；虚拟机到板子 ping/TCP 554 也失败。重启 `/system/wifi/wifi_start.sh RTL8189FS` 后仍拿到同一 DHCP 地址，但数据面仍不通。

已停止 `ittb_stream`/`ittb_control` 释放内存。当前保留 `use_mode=5`，便于网络恢复后继续验证 2M30。若要回滚默认 4M30：

```bash
cd /system/Hi3516CV610_PQ_V1.0.2.0
cp configs/sc4336p/config_entry.ini.orig_20260905 configs/sc4336p/config_entry.ini
```

下一步优先处理网络路径。建议将 VMware 网络改为桥接到与板子相同的物理网卡，或先用 Windows VLC 测试 `rtsp://192.168.0.106:554/0` 是否可达。若 Windows 可达而 VM 不可达，则问题在 VMware NAT/桥接；若 Windows 也不可达，则问题在板端 WiFi/AP 隔离/无线连接本身。

## WiFi 配置写入与当前阻塞（2026-09-05）

已按用户提供的新网络写入板端 WiFi 配置。为避免手动脚本和启动过程读取不同路径，已同步写入：

- `/system/wifi/config/wpa_supplicant.conf`
- `/etc/wifi/config/wpa_supplicant.conf`

原文件备份为：

- `/system/wifi/config/wpa_supplicant.conf.before_20260905_ziroom601`
- `/etc/wifi/config/wpa_supplicant.conf.before_20260905_ziroom601`

未在日志中输出明文密码。`/system/wifi/wifi_start.sh` 实测使用 `/system/wifi/config/wpa_supplicant.conf`，当前 wpa 状态：`ssid=ziroom601`、`key_mgmt=WPA2-PSK`、`wpa_state=COMPLETED`、`ip_address=192.168.0.106`。

为排除旧进程干扰，已清理重复 `udhcpc`/`wpa_supplicant` 并重启 WiFi；随后又实测卸载并重新加载 `/system/wifi/ko/rtl8189fs.ko`，确认 `wlan0` 恢复并重新关联成功。

当前阻塞：板子能认证、能 DHCP、ARP 表能看到网关 `192.168.0.1` 和宿主机 `192.168.0.102`，但板子 ping 网关/宿主机均 100% 丢包；虚拟机 ping/TCP 到板子 `192.168.0.106` 也失败。Windows 侧 VLC 也打不开 RTSP。此时问题不再是 WiFi 密码或配置文件未写入，更像 AP/客户端隔离、路由器无线转发异常、板端 WiFi 驱动数据面异常，或当前网络不允许客户端互通。

建议下一步：

1. 在路由器/公寓 WiFi 管理侧确认是否启用“客户端隔离/AP 隔离/访客网络隔离”。
2. 若可以，换成手机热点或 PC 热点测试，优先使用 2.4GHz、WPA2-PSK、关闭客户端隔离。
3. 或使用 RJ45 有线连接板子，绕开 RTL8189FS WiFi 数据面。
4. 网络恢复后继续验证当前保留的 `2M30` RTSP 模式；若需要恢复默认 4M30，可回滚 `config_entry.ini.orig_20260905`。

## ROS 视觉链路基线验收（2026-09-05）

用户目标调整为先跑通 ROS 整个视觉链路。当前工作空间实际包含两个 ROS 包：`hr_vision` 和 `hr_bridge`。正式方案中的 tracker、task_manager、Nav2 等还没有源码落地，因此本轮可验收的 ROS 链路为：

`Hi3516 RTSP/文件/测试图 -> hr_image_source -> /camera/image_raw -> hr_perception -> /detections + /diagnostics`

`hr_bridge` 只参与构建检查，不启动 STM32 串口桥，不启动导航，不发布速度。

已执行：

```bash
cd /home/luckfox/d2lros2
source Home_robot/upper/vision_env.sh
cd Home_robot/upper/ros2_ws
python -m colcon build --symlink-install
python -m pytest src/hr_vision/test/test_common.py -q
python src/hr_vision/test/verify_pipeline.py   --model /home/luckfox/Hi3516/vision-assets/yolov8n.pt   --image /home/luckfox/Hi3516/vision-assets/bus.jpg
```

结果：`hr_bridge`、`hr_vision` 全量构建通过；`hr_vision` 单测 4 项通过；YOLO/ROS 离线集成测试通过，收到 30 条图像、4 条检测消息，检测到 `person`，并验证源停止后检测失效、旧帧不会重新激活检测，且没有 `/cmd_vel` 或 `/cmd_vel_auto`。

在线 RTSP 当前基线：

- 板端已回滚到 `4M30`，即 `use_mode=0`。
- RTSP 当前可打开，OpenCV 可读到 `2560x1440` 帧。
- 抓图 `Home_robot/upper/captures/hi3516_rtsp_recheck_4m30.jpg` 可被离线 YOLO 识别为透明水杯相关目标：`vase` 0.582、`cup` 0.324。
- 在线 RTSP 进入 ROS 后，图像源和 YOLO 节点均能运行并发布诊断，但当前透明杯近距离画面在缩放后的实时链路中未稳定命中 `cup/vase`。这属于模型/目标姿态/缩放/网络抖动综合问题，不是 ROS 包构建或 topic 链路不可用。

下一步工程动作：

1. 保留 4M30 作为已知可出图基线。
2. 网络侧优先降低 WiFi 抖动：换手机/PC 热点、RJ45，或确认 `ziroom601` 不做客户端隔离。
3. 视觉侧用更稳定的验收目标：完整人体、普通不透明杯子、背景简洁，先用 `output_width=1280, imgsz=640, conf=0.25`。
4. 后续再补 tracker/target topic 或接入正式 `hr_perception` 包；当前 `hr_vision` 已提供 `/camera/image_raw` 和 `/detections` 两个上游接口。

## STM32 Type-C 纯接收验收（2026-09-06）

- Type-C 枚举：`1a86:55d4 USB Single Serial`，序列号 `5B34018995`。
- 稳定设备标识：`/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B34018995-if00`；本次为 `/dev/ttyACM0`。
- 串口参数实测：230400 8N1。
- 10秒只读采集到501个校验正确的 `AA 55 19 10` 状态帧，约50.1 Hz，与现有旧 X-Protocol 匹配。
- `hr_bridge` 已改为不依赖 pyserial 的 Linux 原生串口实现。
- `pyserial 3.5` 已从 Ubuntu Jammy `python3-serial 3.5-1` 安装到当前用户目录
  `/home/luckfox/.local/lib/python3.10/site-packages`；`pc_control` 导入与5项协议单测通过。
- ROS纯接收实测：`stm32_link_ok=true`，`/wheel/odom_raw` 约50.4 Hz，当前速度为0，电池约11.43 V。
- IMU比例未确认，当前发布零值并用 covariance `-1`、`imu_valid=false` 明确标记不可用。
- 旧状态帧没有安全许可、看门狗、控制源、序号和时间戳，保持 `safety_permit=false`、`watchdog_healthy=false`。
- `command_output_enabled=false`，`/cmd_vel` 发布者为0；此次没有向STM32发送任何数据，也未启动底盘。

## OpenCTR H60 V3.61 源码审查（2026-09-06）

- 压缩包已检查并解压到 `firmware/vendor/OpenCTR_H60V36_R750ROS_V3.61.0602/`，原包保留。
- 工程目标为 OpenCTR H60 V3.6 / STM32F407VET6，默认 `ROBOT_MEC`，IMU 为 QMI8658A；
  与正式方案的大疆 C 板 STM32F407IGT6、四轮差速、BMI088/IST8310、CAN 电机链不同。
- 源码确认 ROS USB 串口 230400、状态帧 `0x10`、速度帧 `0x50`、50 Hz 和千倍速度量纲，
  与当前实机纯接收数据一致。
- 源码没有上位机命令超时归零，也未找到实际 IWDG 门控；运动使能默认开启。通信中断时
  可能保持最后一个非零目标，因此禁止当前固件进入 ROS 实车运动测试。
- 审查记录：[docs/OpenCTR_V3.61源码审查.md](docs/OpenCTR_V3.61源码审查.md)。本次未改
  vendor 源码、未编译、未刷写、未发送串口命令。

## 下位机技术方案验证核心（2026-09-06）

- 已按技术方案创建 `lower/` 验证工程，业务模块采用 `monitor_task`、`chassis_task`、
  `imu_task`、`command_task` 命名；它用于快速联调和验证，不修改或替代技术方案，厂商
  源码继续作为 `firmware/vendor/` 下的只读参考。
- V1 协议草案已实现帧头、版本、Payload 长度、序号、时间戳和 CRC-16/CCITT-FALSE；首个
  `CMD_MOTION` 只包含四轮差速需要的 `vx/wz/enable`，不定义 `vy`。
- 已实现 150 ms 上位机命令超时、100 ms 遥控数据超时、遥控回中后接管、任务心跳门、
  上电未见齐三个关键任务心跳时禁止控制、故障锁存与显式清除、安全许可撤销立即清零、
  差速逆解和运行期参数化限幅/斜坡。
- 主机 GCC `-Wall -Wextra -Werror -Wconversion -Wshadow` 构建通过；CTest 通过；
  AddressSanitizer/UBSan 构建和测试通过。
- `hr_bridge/home_protocol.py` 已实现相同 V1 编码和流式解析，共享 `CMD_MOTION` 测试向量
  在 C 与 Python 两端一致，Python 2 项协议测试通过；尚未连接真实串口发送。
- 板级 BSP、FreeRTOS 绑定、C620/M3508 CAN、BMI088/IST8310、HT-10A、急停和 IWDG
  仍待实物参数。当前 `HR_BOARD_CONFIGURED=0`，只生成主机测试，不生成可刷写固件。

## 当前下位机复验（2026-09-06 11:50）

- USB 重新枚举正常：下位机稳定路径仍为
  `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B34018995-if00`，CH344 四路为
  `/dev/ttyACM1`～`/dev/ttyACM4`。
- 纯接收 3.05 秒得到 173 个状态帧；随后 ROS `hr_bridge` 实测
  `/wheel/odom_raw` 稳定约 50.36 Hz，速度为零，电池约 11.43 V。
- `/robot_status` 显示 `stm32_link_ok=true`、`wheel_odom_valid=true`；由于旧固件没有正式
  安全状态且 IMU 量纲尚未冻结，保持 `safety_permit=false`、`watchdog_healthy=false`、
  `imu_valid=false`。
- `/cmd_vel` 发布者为 0，`command_output_enabled=false`，复验期间未发送下位机命令。
- 虚拟机当前没有 `/dev/video*`；Hi3516 图像仍需走 RTSP，且虚拟机网络仍为
  `192.168.164.129/24`，需与相机当前地址建立可达路径后才能在虚拟机复验真实图像链。

重新插拔后的CH344四路映射为 A/B/C/D → `/dev/ttyACM1/2/3/4`。按现有物理接线，HMMD COMC为
`/dev/ttyACM3`，Hi3516调试COMD为 `/dev/ttyACM4`；应优先使用 `/dev/serial/by-id` 和接口号，
不要依赖易变化的ACM编号。

## ROS 短程运动与跟随链 Mock 验收（2026-09-06）

已增加安全联调入口 `hr_bringup/chain_validation.launch.py` 和自动验收脚本
`upper/tools/verify_motion_chain.py`。该入口使用 Mock 状态、里程计和扫描，固定
`hr_bridge transport_enabled=false`、`command_output_enabled=false`，不会打开或写入
真实下位机串口。

实测通过以下链路：

- RViz 等价的 `odom` 坐标系 0.30 m `/goal_pose` 能生成 `/cmd_vel_auto`。
- 已关联的 2.0 m、0.2 rad 模拟目标能生成前进和转向控制；目标停止上报后自动归零。
- 0.20 m 模拟障碍输入后，Collision Monitor 验证替身持续输出零速度。
- `/cmd_vel` 唯一发布者是 `/collision_monitor`，唯一业务订阅者是 `/hr_bridge`；最大线速度
  0.10 m/s，未发现绕过安全节点的发布路径。
- launch 能干净退出，修复了三个 Python 节点在 ROS 上下文关闭后再次发布导致的异常。

执行命令：

```bash
cd /home/luckfox/d2lros2
source Home_robot/upper/vision_env.sh
cd Home_robot/upper/ros2_ws
python ../tools/verify_motion_chain.py
```

输出为 `PASS: bounded RViz goal, target follow, target-loss stop, obstacle stop, unique velocity path`。
这证明 ROS 软件控制路径已经闭合，不代表实车已获准运动；真实 HMMD 没有二维障碍扫描，且
当前 OpenCTR 固件缺少断链停车，因此实车输出仍保持关闭。

## OpenCTR 安全验证副本（2026-09-06）

厂商源码保持不变。另建
`firmware/validation/OpenCTR_H60V36_R750ROS_V3.61.0602_safe/`，加入 200 ms ROS
命令超时归零、上电命令失效、速度帧严格长度检查、串口帧缓冲长度检查，并阻止无关数据帧
抢占 ROS 控制源。Keil 工程文件已引用新增 `ax_failsafe.c`，宿主机测试已通过。

虚拟机没有 Keil/Arm Compiler，因此尚未完成整套固件编译和刷写；当前控制板仍应视为运行
原厂旧固件。可审查补丁位于 `firmware/validation/openctr_v3_61_safe.patch`。

## 2026-09-06 全量回归

- ROS 2 工作区 15 个包 `colcon build --symlink-install` 通过。
- Python 单元/协议/网页测试共 19 项通过。
- `lower/` 主机 GCC 构建和 CTest 通过。
- OpenCTR 超时保护宿主机测试通过。
- 已为 5 个含测试的 ROS Python 包注册 pytest；标准 `colcon test` 现执行 12 项，结果为
  0 错误、0 失败。加上控制协议与网页后端等仓库级测试，本轮 Python 测试共 21 项通过。

## 任务 Action 生命周期验收（2026-09-06）

新增 `upper/tools/verify_task_lifecycle.py`，在独立 ROS domain 中实测任务正常完成、并发忙碌
拒绝、不满足安全条件时拒绝、客户端取消、任务超时和遥控接管中断六条路径，全部通过。
任务接收处增加互斥锁和预约状态，消除两个并发 Goal 在执行回调开始前同时被接受的窗口。

安全准入现在同时要求 `command_fresh=true` 与 `watchdog_healthy=true`。正式入口默认
`mock_navigation_enabled=false`，在地图目标解析器尚未实现时会以
`GOAL_RESOLVER_UNAVAILABLE` 拒绝任务；只有 Mock bringup 显式开启模拟导航。跟随模式的
期望距离和最小安全距离默认均为未配置，参数未显式设置且不满足
`desired_distance > minimum_safe_distance > 0` 时，任务以 `FOLLOW_POLICY_UNCONFIGURED`
拒绝，避免默认向零距离接近目标。

## STM32 桥接伪串口集成验收（2026-09-06）

新增 `upper/tools/verify_bridge_pty.py`，只创建 Linux `/dev/pts/*` 伪串口，不打开任何
`/dev/ttyACM*`。字节级实测已通过：旧 `0x10` 状态帧进入 `/robot_status` 和
`/wheel/odom_raw`，ROS Twist 转成旧 `0x50` 串口帧，输入 1.0 m/s、2.0 rad/s 时被二次
限幅为 0.10 m/s、0.30 rad/s，停止发布超过 0.25 s 后串口持续输出零速度帧。

旧协议输出增加两道显式门：`legacy_firmware_watchdog_verified=true` 和
`bench_motion_authorized=true`。两者默认均为 false；只设置
`command_output_enabled=true` 仍会拒绝启动。它们仅供安全固件刷写后、车轮悬空的临时
台架验证，正式 V1 协议仍必须由 MCU 回报安全许可和看门狗状态。

## USB 串口稳定命名准备（2026-09-06）

已根据当前重新枚举后的真实 udev 属性创建
`config/udev/99-home-robot-serial.rules`：OpenCTR 固定为 `/dev/robot_mcu`，CH344 COMC
固定为 `/dev/hmmd_sensor`，COMD 固定为 `/dev/hi3516_debug`，并赋予当前用户所属
`plugdev` 组读写权限。安装脚本位于 `config/udev/install_serial_rules.sh`。

规则文件和脚本已完成语法及设备属性核对，但安装到 `/etc/udev/rules.d` 需要管理员权限，
当前无免密 sudo，因此系统规则尚未改变。
