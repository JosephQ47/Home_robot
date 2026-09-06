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
  * @内  容  PWM接口舵机控制
  *
  ******************************************************************************
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __AX_SERVO_H
#define __AX_SERVO_H

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx.h"

// 接口函数
void AX_SERVO_S1234_Init(void);              //舵机接口初始化
void AX_SERVO_S1_SetAngle(int16_t angle);    //舵机控制   
void AX_SERVO_S1_Release(void);              //舵机释放
void AX_SERVO_S2_SetAngle(int16_t angle);    //舵机控制
void AX_SERVO_S2_Release(void);              //舵机释放
void AX_SERVO_S3_SetAngle(int16_t angle);    //舵机控制  
void AX_SERVO_S3_Release(void);              //舵机释放
void AX_SERVO_S4_SetAngle(int16_t angle);    //舵机控制
void AX_SERVO_S4_Release(void);              //舵机释放

void AX_SERVO_S5_Init(void);                 //舵机接口初始化
void AX_SERVO_S5_SetAngle(int16_t angle);    //舵机控制 
void AX_SERVO_S5_Release(void);              //舵机释放

void AX_SERVO_S6_Init(void);                 //舵机接口初始化
void AX_SERVO_S6_SetAngle(int16_t angle);    //舵机控制  
void AX_SERVO_S6_Release(void);              //舵机释放



#endif

/******************* (C) 版权 2026 XTARK **************************************/

