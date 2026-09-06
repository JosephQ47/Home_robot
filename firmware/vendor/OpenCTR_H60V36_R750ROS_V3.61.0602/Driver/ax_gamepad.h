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
  * @内  容  USB无线手柄函数文件
  *
  ******************************************************************************
  * @说  明
  * 
  ******************************************************************************
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __AX_GAMEPAD_H
#define __AX_GAMEPAD_H

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx.h"
#include <stdint.h>

#include "usbh_hid.h"
#include "usbh_hid_gamepad.h"
#include "usb_host.h"

//手柄产品PID、VID
#define GAMEPAD_VID 0x045E
#define GAMEPAD_PID 0x028E

//手柄按键定义
#define  GP_KEY1_UP         0x01    //方向 上按键
#define  GP_KEY1_DOWN       0x02    //方向 下按键 
#define  GP_KEY1_LEFT       0x04    //方向 右按键
#define  GP_KEY1_RIGHT      0x08    //方向 左按键
#define  GP_KEY1_START      0x10    //START 按键
#define  GP_KEY1_SELECT     0x20    //SELECT 按键
#define  GP_KEY1_LJOY       0x40    //左摇杆 按键
#define  GP_KEY1_RJOY       0x80    //右摇杆 按键 

#define  GP_KEY2_L1         0x01    //L1 按键
#define  GP_KEY2_R1         0x02    //L2 按键
#define  GP_KEY2_MODE       0x04    //MODE 按键
#define  GP_KEY2_A          0x10    //功能 A按键
#define  GP_KEY2_B          0x20    //功能 B按键
#define  GP_KEY2_X          0x40    //功能 X按键
#define  GP_KEY2_Y          0x80    //功能 Y按键

//手柄键值数据结构体	 
typedef struct
{
  uint8_t K1;         

  uint8_t K2;         
	
   int8_t LX;      /* 左边摇杆  -128 = 左    127 = 右   */

   int8_t LY;      /* 左边摇杆  -128 = 下    127 = 上   */	

   int8_t RX;      /* 右边摇杆  -128 = 左    127 = 右   */

   int8_t RY;      /* 右边摇杆  -128 = 下    127 = 上   */

  uint8_t LT;      /* 左边油门  0 = 抬起    0xff = 按下   */

  uint8_t RT;      /* 右边油门  0 = 抬起    0xff = 按下   */
	
}GAMEPAD_Type_t;


// 接口函数
void GAMEPAD_InsertCallback(void);   //手柄插入回调函数
void GAMEPAD_PullOutCallback(void);  //手柄插入回调函数
void GAMEPAD_Decode(USBH_HandleTypeDef *phost,uint8_t* buffer,uint8_t datalen);  //手柄数据解析

//通用游戏手柄接口
extern GAMEPAD_Type_t GamePad;

#endif 

/******************* (C) 版权 2026 XTARK **************************************/
