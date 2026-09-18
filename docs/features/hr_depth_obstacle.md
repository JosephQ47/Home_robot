# 功能设计：hr_depth_obstacle（深度点云质量门控与地面滤除）

- 状态：待评审
- 基准条款：技术方案 §2.2 主逻辑 2/3、§3.2、§10.2「深度障碍与目标跟踪」、§10.4
- 起草：AI；签字：__________ 日期：__________

## 1. 范围

把 Gemini 2 的原始点云，变成 Nav2 局部代价地图可以安全使用的**辅助**障碍观测。

它是 S3 `/scan` 的补充，**不是替代**：二维 SLAM、定位和 Collision Monitor 停止区
仍然只用 `/scan`。Gemini 2 离线时，S3 二维导航必须能继续运行。

## 2. 接口契约

| 方向 | 名称 | 类型 |
|---|---|---|
| 订阅 | `/camera/depth/points` | `sensor_msgs/PointCloud2` |
| 订阅 | `/camera/depth/camera_info` | `sensor_msgs/CameraInfo` |
| 发布 | `/obstacle/depth_points` | `sensor_msgs/PointCloud2`（已滤除地面与无效点） |
| 发布 | `/diagnostics` | 深度有效率、地面滤除比例、过期状态 |

## 3. 处理流水线

```text
原始点云 → 新鲜度门控 → 距离门控 → 有效像素比例门控
        → 地面平面滤除 → 高度窗口门控 → 体素下采样 → 发布
```

## 4. 行为规则

| 编号 | 规则 |
|---|---|
| DO-1 | 点云时间戳超过 `cloud_timeout_ms` 即停止发布，**不复用旧点云**。 |
| DO-2 | 有效点比例低于 `min_valid_ratio` 时，判定该帧不可信，不发布并上报诊断降级。 |
| DO-3 | 只保留 `[min_range_m, max_range_m]` 区间内的点；超出深度相机有效量程的点一律丢弃。 |
| DO-4 | 地面滤除按 `ground_height_m ± ground_tolerance_m` 执行；滤除比例异常（过高或过低）时上报诊断。 |
| DO-5 | 只保留 `[obstacle_min_height_m, obstacle_max_height_m]` 高度窗口内的点，避开天花板与地面残留。 |
| DO-6 | 输出话题**只**作为 Nav2 局部代价地图的额外 observation source，不接入 Collision Monitor。 |
| DO-7 | 透明、高反光目标产生的深度空洞不得被当成「无障碍」；空洞区域按未知处理，不清除代价地图已有障碍。 |

## 5. 验收标准

| 编号 | 判据 |
|---|---|
| AC-1 | 地面平整场景下输出点云不含地面点（可视化 + 点数统计） |
| AC-2 | 遮挡相机后 `cloud_timeout_ms` 内停止发布 |
| AC-3 | 关闭 Gemini 2，S3 二维导航链路仍可完整跑通 |
| AC-4 | 高低障碍（矮凳、桌沿）在局部代价地图中出现，且 `/scan` 单独不可见 |
| AC-5 | 单元测试覆盖 DO-1…DO-5 的边界（等于阈值可用、超阈值 1 单位失效） |

## 6. 本次交付边界

交付节点骨架 + 配置 + 门控逻辑单元测试。地面高度、量程、有效率阈值均为**待实测冻结**初值。
