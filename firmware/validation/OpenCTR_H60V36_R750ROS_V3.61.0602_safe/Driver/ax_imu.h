/**			                                                    
		   ____                    _____ _______ _____       XTARK@塔克创新
		  / __ \                  / ____|__   __|  __ \ 
		 | |  | |_ __   ___ _ __ | |       | |  | |__) |
		 | |  | | '_ \ / _ \ '_ \| |       | |  |  _  / 
		 | |__| | |_) |  __/ | | | |____   | |  | | \ \ 
		  \____/| .__/ \___|_| |_|\_____|  |_|  |_|  \_\
				| |                                     
				|_|                OpenCTR   机器人控制器
									 
  ****************************************************************************** 
  *           
  * 版权所有： XTARK@塔克创新  版权所有，盗版必究
  * 公司网站： www.xtark.cn   www.tarkbot.com
  * 淘宝店铺： https://xtark.taobao.com  
  * 塔克微信： 塔克创新（关注公众号，获取最新更新资讯）
  *      
  ******************************************************************************
  * @作  者  塔克创新团队
  * @内  容  IMU三轴加速度三轴陀螺仪操作
  *
  ******************************************************************************
  */
  
  
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __AX_IMU_H
#define __AX_IMU_H

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx.h"

//QMI8658地址 SA0=1 地址为：0X6A, SA0=0 地址为：0X6B *
#define QMI8658_ADDR     0X6A     

//QMI8658使能开关
#define QMI_ACCGYR_DISABLE  (0x00)   // 不使能陀螺仪和加速度计 
#define QMI_ACC_ENABLE      (0x01)   // 使能加速度计 
#define QMI_GYR_ENABLE      (0x02)   // 使能陀螺仪 
#define QMI_ACCGYR_ENABLE   (0x03)   // 使能陀螺仪和加速度计 

//IO方向设置
#define SDA_IN()  {GPIOB->MODER&=~(3<<(7*2));GPIOB->MODER|=0<<7*2;}	 //输入模式
#define SDA_OUT() {GPIOB->MODER&=~(3<<(7*2));GPIOB->MODER|=1<<7*2;}  //输出模式

//IO操作函数	 
#define IIC_SCL    PBout(6) //SCL
#define IIC_SDA    PBout(7) //SDA	 
#define READ_SDA   PBin(7)  //输入SDA 

//QMI8658A的寄存器地址 
enum QMI_Reg
{
    REG_WHOAMI        = 0,  // 芯片设备 ID 寄存器 (默认值通常为 0x05)
    REG_REVISION      = 1,  // 芯片版本号寄存器
    REG_CTRL1         = 2,  // 控制寄存器1 (配置 SPI/I2C 接口、地址自动递增等)
    REG_CTRL2         = 3,  // 控制寄存器2 (加速度计配置：量程 FS、输出数据速率 ODR)
    REG_CTRL3         = 4,  // 控制寄存器3 (陀螺仪配置：量程 FS、输出数据速率 ODR)
    REG_RESERVED      = 5,  // 保留寄存器
    REG_CTRL5         = 6,  // 控制寄存器5 (传感器数据低通滤波 LPF 配置)
    REG_RESERVED1     = 7,  // 保留寄存器1
    REG_CTRL7         = 8,  // 控制寄存器7 (全局使能控制：唤醒传感器、使能姿态引擎等)
    REG_CTRL8         = 9,  // 控制寄存器8 (手势/动作检测与中断映射配置)
    REG_CTRL9         = 10, // 控制寄存器9 (主机命令 CTRL9 寄存器，用于发送控制指令)

    // --- 内部校准寄存器 ---
    REG_CAL1_L        = 11, // 校准数据1 低字节
    REG_CAL1_H        = 12, // 校准数据1 高字节
    REG_CAL2_L        = 13, // 校准数据2 低字节
    REG_CAL2_H        = 14, // 校准数据2 高字节
    REG_CAL3_L        = 15, // 校准数据3 低字节
    REG_CAL3_H        = 16, // 校准数据3 高字节
    REG_CAL4_L        = 17, // 校准数据4 低字节
    REG_CAL4_H        = 18, // 校准数据4 高字节

    // --- FIFO 控制与状态 ---
    REG_FIFOWMKTH     = 19, // FIFO 水位阈值寄存器 (Watermark Threshold)
    REG_FIFOCTRL      = 20, // FIFO 控制寄存器 (工作模式和大小配置)
    REG_FIFOCOUNT     = 21, // FIFO 当前数据量计数器 (已存储的样本数)
    REG_FIFOSTATUS    = 22, // FIFO 状态寄存器 (空、满、溢出等标志)
    REG_FIFODATA      = 23, // FIFO 数据读取寄存器 (从中连续读取 FIFO 数据)

    // --- 系统状态与中断 ---
    REG_STATUSINT     = 45, // 中断状态寄存器 (指示发生了哪种中断)
    REG_STATUS0       = 46, // 状态寄存器0 (传感器数据就绪标志 Data Ready)
    REG_STATUS1       = 47, // 状态寄存器1 (各类动作引擎的触发状态)

    // --- 时间戳数据 ---
    REG_TIMESTAMP_L   = 48, // 时间戳 低字节
    REG_TIMESTAMP_M   = 49, // 时间戳 中字节
    REG_TIMESTAMP_H   = 50, // 时间戳 高字节

    // --- 传感器原始数据 ---
    REG_TEMPERATURE_L = 51, // 温度传感器数据 低字节
    REG_TEMPERATURE_H = 52, // 温度传感器数据 高字节
    REG_AX_L          = 53, // 加速度计 X轴 低字节
    REG_AX_H          = 54, // 加速度计 X轴 高字节
    REG_AY_L          = 55, // 加速度计 Y轴 低字节
    REG_AY_H          = 56, // 加速度计 Y轴 高字节
    REG_AZ_L          = 57, // 加速度计 Z轴 低字节
    REG_AZ_H          = 58, // 加速度计 Z轴 高字节
    REG_GX_L          = 59, // 陀螺仪 X轴 低字节
    REG_GX_H          = 60, // 陀螺仪 X轴 高字节
    REG_GY_L          = 61, // 陀螺仪 Y轴 低字节
    REG_GY_H          = 62, // 陀螺仪 Y轴 高字节
    REG_GZ_L          = 63, // 陀螺仪 Z轴 低字节
    REG_GZ_H          = 64, // 陀螺仪 Z轴 高字节

    // --- 姿态引擎 (AE) 与动作数据 ---
    REG_COD_STATUS    = 70, // 计步器/动作检测状态寄存器
    REG_DQW_L         = 73, // 四元数 W分量 低字节
    REG_DQW_H         = 74, // 四元数 W分量 高字节
    REG_DQX_L         = 75, // 四元数 X分量 低字节
    REG_DQX_H         = 76, // 四元数 X分量 高字节
    REG_DQY_L         = 77, // 四元数 Y分量 低字节
    REG_DQY_H         = 78, // 四元数 Y分量 高字节
    REG_DQZ_L         = 79, // 四元数 Z分量 低字节
    REG_DQZ_H         = 80, // 四元数 Z分量 高字节
    REG_DVX_L         = 81, // 速度增量(Delta Velocity) X轴 低字节
    REG_DVX_H         = 82, // 速度增量 X轴 高字节
    REG_DVY_L         = 83, // 速度增量 Y轴 低字节
    REG_DVY_H         = 84, // 速度增量 Y轴 高字节
    REG_DVZ_L         = 85, // 速度增量 Z轴 低字节
    REG_DVZ_H         = 86, // 速度增量 Z轴 高字节

    // --- 动作检测与复位 ---
    REG_TAP_STATUS    = 89, // 敲击检测状态寄存器
    REG_STEP_CNT_L    = 90, // 计步器步数 低字节
    REG_STEP_CNT_M    = 91, // 计步器步数 中字节
    REG_STEP_CNT_H    = 92, // 计步器步数 高字节
    REG_RESET         = 96  // 软件复位寄存器 (写入特定值如 0xB0 触发软复位)
};

//Ctrl9详细命令说明 
enum QMI_Ctrl9Command
{
    CTRL9_CMD_ACK                   = 0X00,
    CTRL9_CMD_RSTFIFO               = 0X04,
    CTRL9_CMD_REQFIFO               = 0X05, /* Get FIFO data from Device */
    CTRL9_CMD_WOM_SETTING           = 0x08, /* 设置并启用运动唤醒 */
    CTRL9_CMD_ACCELHOSTDELTAOFFSET  = 0x09, /* 更改加速度计偏移 */
    CTRL9_CMD_GYROHOSTDELTAOFFSET   = 0x0A, /* 更改陀螺仪偏移 */
    CTRL9_CMD_CFGTAP                = 0x0C, /* 配置TAP检测 */
    CTRL9_CMD_CFGPEDESTRIAN         = 0x0D, /* 配置计步器 */
    CTRL9_CMD_MOTION                = 0x0E, /* 配置任何运动/无运动/显着运动检测 */
    CTRL9_CMD_RSTPEDESTRIAN         = 0x0F, /* 重置计步器计数（步数） */
    CTRL9_CMD_COPYUSID              = 0x10, /* 将 USID 和 FW 版本复制到 UI 寄存器 */
    CTRL9_CMD_SETRPU                = 0x11, /* 配置 IO 上拉 */
    CTRL9_CMD_AHBCLOCKGATING        = 0x12, /* 内部 AHB 时钟门控开关 */
    CTRL9_CMD_ONDEMANDCALIVRATION   = 0xA2, /* 陀螺仪按需校准 */
    CTRL9_CMD_APPLYYROGAINS         = 0xAA  /* 恢复保存的陀螺仪增益 */
};


//加速度计和陀螺仪的低通过滤器模式选择
enum QMI_LpfMode
{
    LSPA_MODE_0 = 0x00 << 1,
    LSPA_MODE_1 = 0x01 << 1,
    LSPA_MODE_2 = 0x02 << 1,
    LSPA_MODE_3 = 0x03 << 1,

    LSPG_MODE_0 = 0x00 << 5,
    LSPG_MODE_1 = 0x01 << 5,
    LSPG_MODE_2 = 0x02 << 5,
    LSPG_MODE_3 = 0x03 << 5
};

//加速度计量程选择
enum QMI_AccRange
{
    ACCRANGE_2G  = 0x00 << 4,
    ACCRANGE_4G  = 0x01 << 4,
    ACCRANGE_8G  = 0x02 << 4,
    ACCRANGE_16G = 0x03 << 4
};

/* 加速度计ODR输出速率选择 */
enum QMI_AccOdr
{
    ACCODR_8000HZ = 0x00,
    ACCODR_4000HZ = 0x01,
    ACCODR_2000HZ = 0x02,
    ACCODR_1000HZ = 0x03,
    ACCODR_500HZ = 0x04,
    ACCODR_250HZ = 0x05,
    ACCODR_125HZ = 0x06,
    ACCODR_62_5HZ = 0x07,
    ACCODR_31_25HZ = 0x08,
	
    ACCODR_LOWPOWER_128HZ = 0x0c,
    ACCODR_LOWPOWER_21HZ = 0x0d,
    ACCODR_LOWPOWER_11HZ = 0x0e,
    ACCODR_LOWPOWER_3HZ = 0x0f
};

//陀螺仪量程选择 
enum QMI_GyrRange
{
    GYRRANGE_16DPS   = 0 << 4,
    GYRRANGE_32DPS   = 1 << 4,
    GYRRANGE_64DPS   = 2 << 4,
    GYRRANGE_128DPS  = 3 << 4,
    GYRRANGE_256DPS  = 4 << 4,
    GYRRANGE_512DPS  = 5 << 4,
    GYRRANGE_1024DPS = 6 << 4,
    GYRRANGE_2048DPS = 7 << 4
};

//陀螺仪输出速率选择
enum Qmi_GyrOdr
{
    GYRODR_8000HZ = 0x00,
    GYRODR_4000HZ = 0x01,
    GYRODR_2000HZ = 0x02,
    GYRODR_1000HZ = 0x03,
    GYRODR_500HZ  = 0x04,
    GYRODR_250HZ  = 0x05,
    GYRODR_125HZ  = 0x06,
    GYRODR_62_5HZ = 0x07,
    GYRODR_31_25HZ = 0x08
};


// 接口函数
void AX_IMU_Init(void);    //IMU传感器初始化
void AX_IMU_ConfigAcc(enum QMI_AccRange range, enum QMI_AccOdr odr, enum QMI_LpfMode mode);  //设置加速度参数
void AX_IMU_ConfigGyro(enum QMI_GyrRange range, enum Qmi_GyrOdr odr, enum QMI_LpfMode mode);  //设置陀螺仪参数
void AX_IMU_GetAccData(int16_t *pbuf);    //获取加速度寄存器输出值
void AX_IMU_GetGyroData(int16_t *pbuf);   //获取陀螺仪寄存器输出值
void AX_IMU_GetTempData(int16_t *pbuf);   //获取温度寄存器输出值


#endif

/******************* (C) 版权 2026 XTARK **************************************/
