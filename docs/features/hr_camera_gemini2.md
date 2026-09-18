# 功能设计：相机链路迁移（Hi3516/SC4336P UVC → Orbbec Gemini 2）

- 状态：待评审
- 基准条款：技术方案 §1 硬件基线、§2.3、§3.2、§10.2「Gemini 2 感知链」、§10.4
- 起草：AI；签字：__________ 日期：__________

## 1. 变更实质

旧方案的图像源是 **Hi3516CV610 + SC4336P 的 USB UVC 二维相机**，只有 RGB。
新方案换成 **Orbbec Gemini 2 主动双目深度相机**，同时提供
RGB、深度图、IR、相机 IMU 和三维点云。

这不是换个型号那么简单——它引入了**深度**这条全新数据通路，
使 `hr_target_tracker` 从「二维框 + 雷达角窗估距」升级为「同帧深度直接估距」，
并使 `hr_depth_obstacle` 成为可能。

## 2. 话题命名迁移

| 旧 | 新 | 说明 |
|---|---|---|
| `/camera/image_raw` | `/camera/color/image_raw` | 与 Orbbec ROS 2 驱动默认命名对齐 |
| （无） | `/camera/color/camera_info` | AprilTag 与深度关联必需 |
| （无） | `/camera/depth/image_raw` | 深度图 |
| （无） | `/camera/depth/points` | 点云，送 `hr_depth_obstacle` |
| （无） | `/camera/depth/camera_info` | 深度内参 |
| 节点 `/hi3516_camera_driver` | 节点 `/hr_camera` | 驱动节点更名 |

设备名通过 udev 固定为 `/dev/gemini2`。

## 3. 对下游的影响

| 下游 | 影响 |
|---|---|
| `hr_perception` | 输入话题改名；仍输出 `/detections`（`Detection2DArray`） |
| `hr_target_tracker` | **优先使用同帧深度估距**，深度无效时才回落到 S3 同方向角窗/点簇交叉验证 |
| `hr_docking` | 新增消费者：RGB + `CameraInfo` → AprilTag |
| `hr_depth_obstacle` | 新增消费者：点云 |
| `hr_hmmd` | 新方案中不存在该链路，标记为**历史临时替代件**，不再纳入正式部署图 |

## 4. 不变的边界

- 深度相机**不参与**二维 SLAM 定位。
- 深度相机**不替代**激光安全扫描；Collision Monitor 停止区仍只用 `/scan`。
- 视觉结果**不得**进入 `hr_bridge` 或下位机控制链。

## 5. 验收标准

| 编号 | 判据 |
|---|---|
| AC-1 | RGB/深度/点云/`CameraInfo` 的时间戳、帧号和有效性可监控 |
| AC-2 | USB 拔插 20 次可恢复；连续 24 小时无不可恢复断流 |
| AC-3 | 相机断流、RGB/深度不同步或深度有效率不足时，旧三维结果不得继续触发事件 |
| AC-4 | 关闭 Gemini 2 后，S3 二维导航链路仍完整可用（降级而非瘫痪） |
| AC-5 | 帧率/延迟/有效率实测数值落盘，不以估算值替代 |

## 6. 本次交付边界

Gemini 2 实物标定外参、档位、帧同步误差均**待实测冻结**。
本次交付话题命名迁移、udev 规则骨架、配置项和下游改名，不含实机标定数据。
