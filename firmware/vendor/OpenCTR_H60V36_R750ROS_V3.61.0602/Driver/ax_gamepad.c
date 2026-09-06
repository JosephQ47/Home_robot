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
  * @内  容  USB手柄函数文件
  *
  ******************************************************************************
  * @说  明
  * 
  ******************************************************************************
  */

#include "ax_gamepad.h"
#include "ax_robot.h"

//手柄摇杆键值结构体
GAMEPAD_Type_t GamePad;

/**
  * @简  述  手柄设备插入函数_任务环境
  * @参  数  无
  * @返回值  无
  */
void GAMEPAD_InsertCallback(void)
{
	//添加插入手柄动作

	
	//执行蜂鸣器鸣叫提示
	ax_beep_ring = BEEP_SHORT;

	//打印调试信息
	//printf("插入USB \r\n");
}


/**
  * @简  述  手柄设备拔出_任务环境
  * @参  数  无
  * @返回值  无
  */
void GAMEPAD_PullOutCallback(void)
{
	//添加拔出手柄动作
	
	
	//执行蜂鸣器鸣叫提示
	ax_beep_ring = BEEP_LONG;

     //打印调试信息
	//printf("拔出USB \r\n");
}


/**
  * @简  述  游戏手柄数据解码
  * @参  数  无
  * @返回值  无
  */
void GAMEPAD_Decode(USBH_HandleTypeDef *phost,uint8_t* buffer,uint8_t datalen)
{
	//解析手柄数据
	GamePad.K1 = buffer[2];
	GamePad.K2 = buffer[3];	
	GamePad.LT = buffer[4];
	GamePad.RT = buffer[5];	
	GamePad.LX = (int8_t)buffer[7];
	GamePad.LY = (int8_t)buffer[9];
	GamePad.RX = (int8_t)buffer[11];
	GamePad.RY = (int8_t)buffer[13];
	
	//不在GPD控制模式下
	if(ax_control_mode != CTL_GPD)
	{
		//判断是否开启手柄控制
		//START按键被按下后，左边摇杆上推，进入手柄控制模式
		if((GamePad.K1 == GP_KEY1_START) && (GamePad.LY == 127))
		{
			//切换到手柄模式
			ax_control_mode = CTL_GPD;	

			//执行蜂鸣器鸣叫提示
			ax_beep_ring = BEEP_SHORT;
		}
	}
	
	//打印调试信息
	//printf("GP:%2x %2x %2x %2x | ",MyGamePad.K1,MyGamePad.K2,MyGamePad.LT,MyGamePad.RT);
	//printf("%d %d %d %d \r\n",MyGamePad.LX,MyGamePad.LY,MyGamePad.RX,MyGamePad.RY);
}


/******************* (C) 版权 2026 XTARK **************************************/
