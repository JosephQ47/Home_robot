# Core 接入点

这里承载 STM32F407IGT6 启动、HAL 初始化、ISR 和 FreeRTOS 内核接入。实物引脚和 CubeMX 工程尚未核对，因此暂不放置可能被误刷的启动代码。ISR 只能搬运数据、记录时间戳并通知任务。
