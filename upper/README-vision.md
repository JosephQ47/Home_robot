# Ubuntu PC 视觉调试链路

正式技术方案不变。当前 PC 的 Ubuntu 虚拟机临时代替 RK3588：UVC/RTSP/文件 → 图像话题 → CPU YOLO → 检测话题。Windows 可继续训练模型；若 UVC 摄像头被 Windows 独占，YOLO/控制程序也可以先在 Windows 侧接摄像头。本阶段不涉及 RKNN。

## 当前环境与启动

环境准备于 `/home/luckfox/Hi3516`，不占用 SDK 资料接收目录：

- `vision-venv`：Python 3.10 虚拟环境，允许访问系统 ROS Python 依赖；核心版本见 `vision-requirements.txt`，CPU Torch 2.5.1、Torchvision 0.20.1。
- `ros-deps/root/opt/ros/humble`：从 ROS 官方 apt 仓库下载并解包的 `vision_msgs` 4.1.1。没有管理员权限，因此未安装到系统 `/opt/ros`。`vision_env.sh` 补充 Python、ament 和动态库路径；构建时该前缀没有 `local_setup` 的提示是预期现象。
- `vision-assets/yolov8n.pt`：官方预训练权重；`bus.jpg`：官方示例图，仅用于人员检测验收，不是本开发板实拍。

在项目根目录构建：

```bash
source Home_robot/upper/vision_env.sh
cd Home_robot/upper/ros2_ws
python -m colcon build --packages-select hr_camera hr_perception --symlink-install
source install/local_setup.bash
```

新终端从项目根目录启动离线视觉链路：

```bash
source Home_robot/upper/vision_env.sh
export ROS_DOMAIN_ID=61 ROS_LOCALHOST_ONLY=1
ros2 launch hr_camera camera.launch.py \
  source:=/home/luckfox/Hi3516/vision-assets/bus.jpg \
  model:=/home/luckfox/Hi3516/vision-assets/yolov8n.pt
```

`Ctrl+C` 停止。该 launch 只包含图像接收和检测节点，不启动串口桥、Nav2 或底盘控制。61 是本次隔离调试使用的域；检查终端须设置相同的 ROS 环境。

UVC 枚举成功后，可直接把 `source` 设为 Linux 设备路径，并要求 OpenCV 通过 V4L2 设置 YUYV 640×480@30：

```bash
source Home_robot/upper/vision_env.sh
cd Home_robot/upper/ros2_ws
source install/local_setup.bash
export ROS_DOMAIN_ID=61 ROS_LOCALHOST_ONLY=1
ros2 launch hr_camera camera.launch.py \
  source:=/dev/video0 \
  capture_width:=640 capture_height:=480 capture_fps:=30 \
  pixel_format:=YUYV \
  model:=/home/luckfox/Hi3516/vision-assets/yolov8n.pt
```

如果 PC 端先走 Windows 接收，Ubuntu 虚拟机看不到 `/dev/video*` 是正常的；这时 YOLO/控制程序要在 Windows 侧接摄像头，或把 UVC 设备在 VMware 菜单中独占连接给虚拟机。Linux 验证枚举建议先看：

```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

RTSP 仍可作为保底路径。板上网络与 RTSP 服务可用后，把 `source` 换成当次确认的 URL，例如 `rtsp://<当前板址>:554/0`。这不是已验证在线的地址。支持本地视频路径、静态图和 `synthetic` 测试画面；测试画面不伪造人员检测。RTSP 优先 TCP，连接/读取超时 3 秒，断开后间隔 2 秒重连。本地视频默认 EOF 停止，单独运行接收节点时可设置 `loop:=true`。

检查话题：

```bash
ros2 topic hz /camera/image_raw
ros2 topic echo /detections --once
ros2 topic echo /diagnostics --once
```

## 接口与限制

| 节点 | 输入 | 输出 |
|---|---|---|
| `hr_image_source` | UVC `/dev/video*`、RTSP、文件或测试画面 | `/camera/image_raw`：`sensor_msgs/Image`，BGR8、sensor-data QoS；`/diagnostics` |
| `hr_perception` | `/camera/image_raw` | `/detections`：`vision_msgs/Detection2DArray`；`/diagnostics` |

- 默认 ROS 图像等比例缩小至宽度不超过 640（`output_width=0` 保留原尺寸）、图像发布上限 5 Hz、推理上限 2 Hz、推理输入尺寸 320、CPU 线程 2、阈值 0.35、类别 `person` 与 `cup`。这些是 PC 调试参数，不修改板上编码配置，也不是性能承诺。
- 模型参数必须指向已有本地权重，不隐式下载。替换自训权重时同步修改 `classes`；模型不包含所选类别时明确报错。
- 框坐标使用 `/camera/image_raw` 图像像素（开启缩小时为缩小后的坐标）；`class_id` 存模型标签名称，置信度为模型输出。未分配追踪 ID、未推算距离。
- 图像时间戳是 PC 接收/解码时间，不是 Sensor 曝光时间；检测继承图像 header。UVC、RTSP 服务端、编码器和解码器内部缓存造成的延迟仍需实测，不能仅以接收后新鲜度证明端到端低延迟。
- 应用只保留最新帧；源消息或推理结果超过 2 秒则不作为有效结果发布。失效时发布一次空检测并持续报告诊断，恢复后处理新帧。消费者也必须实现超时，不能永久保留最后一次检测。
- 尚未标定，不发布伪造 `CameraInfo` 或相机安装 TF。此阶段不能做可靠方向计算、雷达关联或目标跟随。
- 没有实现目标出现/消失业务事件门控；此版本只验收图像与检测接口。

## 测试

2026-09-05 本机实测结果：

| 检查 | 结果 |
|---|---|
| `colcon build --packages-select hr_camera hr_perception --symlink-install` | 通过 |
| 单元测试 | 4 项通过：最新帧覆盖、新鲜度、框坐标/标签、空与非法检测 |
| 真实 YOLO + ROS 联调 | 通过；最终一次观察到 28 条图像、7 条检测消息，检测到 person |
| 停止源、注入过期图像、恢复源 | 检测失效、拒绝旧帧、恢复检测均通过 |
| 本地 MJPEG AVI 文件 | 收到 40 帧；EOF 后不再重复旧帧，诊断转 WARN |
| `ros2 launch` 与 Ctrl+C | 产生真实检测；两个节点正常退出，launch 返回 0 |
| 实时海思 UVC / RTSP / 杯子实拍 | 尚未验收；UVC sample 侧已编译，descriptor 脚本和 USB 枚举待确认 |

推理耗时诊断曾记录 376.1 ms、476.7 ms，受虚拟机负载影响；不是平均帧率、端到端延迟或 RK3588 性能。测试结束已停止测试进程。

权重 SHA256：`f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`。
示例图 SHA256：`c02019c4979c191eb739ddd944445ef408dad5679acab6fd520ef9d434bfbc63`。
虚拟环境已安装包快照在 `/home/luckfox/Hi3516/vision-assets/environment-freeze.txt`，不包含从系统继承的 ROS 包。

```bash
source Home_robot/upper/vision_env.sh
python -m pytest Home_robot/upper/ros2_ws/src/hr_perception/test/test_common.py -q
ROS_DOMAIN_ID=61 ROS_LOCALHOST_ONLY=1 python \
  Home_robot/upper/ros2_ws/src/hr_perception/test/verify_pipeline.py \
  --model /home/luckfox/Hi3516/vision-assets/yolov8n.pt \
  --image /home/luckfox/Hi3516/vision-assets/bus.jpg
```

集成测试实际运行 YOLO，检查人类检测、消息 header、停止源后失效、旧图像拒绝与重启源后恢复，并确认隔离域没有速度话题。自动停止所启动的测试进程。杯子标签支持不等同于杯子实拍验收。

## 其他 ROS 节点的准备状态

| 模块 | 当前状态 / 下一步 |
|---|---|
| 图像接收、感知 | 本轮新增 PC 调试实现；现场 RTSP 和杯子实拍待验收 |
| `hr_bridge` | 已有旧协议实现；话题 `/wheel_odom`、`/imu/data_raw` 与方案有差异，且启动就会发送控制帧，未纳入本轮 launch |
| `hr_web_ui` | 已有独立网页和 Mock 后端；真实 ROS Action 适配未实现 |
| `hr_interfaces`、`hr_task_manager` | 需按技术方案冻结消息/Action 与任务前置条件，不能把 Mock 状态当作机器人已执行 |
| `hr_target_tracker` | 待相机标定、安装 TF 和 RPLIDAR 实测后实现；检测框不能直接生成速度 |
| `robot_state_publisher` | 待真实安装尺寸和 URDF；不填猜测的相机/雷达外参 |
| RPLIDAR A1、EKF | 待设备接入及 STM32 状态接口、单位和时间戳核对 |
| SLAM / AMCL / Nav2 / Collision Monitor | 部分依赖已安装，不等同于 Home_robot 集成完成；需先完成传感、TF、里程计与安全链 |
| 完整 `hr_bringup` | 待上述节点分阶段验收后编排；本轮只提供独立视觉 launch |

## 依赖重建与资料来源

有管理员权限的新 Ubuntu 22.04 环境可安装 `python3-venv`、ROS Humble 的 `vision-msgs`、`cv-bridge` 后创建 `--system-site-packages` 虚拟环境；本机因缺少 ensurepip，使用 PyPA 官方 get-pip 在已有虚拟环境内引导 pip。没有升级系统 Python 包。

虚拟环境内安装 CPU Torch 后执行 `python -m pip install -r Home_robot/upper/vision-requirements.txt`。使用 `vision_env.sh` 进入已准备环境；所有路径可通过 `HR_VISION_HOME` 指定另一准备目录。

- 模型接口：[Ultralytics Predict](https://docs.ultralytics.com/modes/predict/)
- ROS 消息：[Humble Detection2DArray](https://docs.ros.org/en/ros2_packages/humble/api/vision_msgs/msg/Detection2DArray.html)
- 权重下载：https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
- 测试图：https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/assets/bus.jpg

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
python -m pytest src/hr_perception/test/test_common.py -q
python src/hr_perception/test/verify_pipeline.py   --model /home/luckfox/Hi3516/vision-assets/yolov8n.pt   --image /home/luckfox/Hi3516/vision-assets/bus.jpg
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

