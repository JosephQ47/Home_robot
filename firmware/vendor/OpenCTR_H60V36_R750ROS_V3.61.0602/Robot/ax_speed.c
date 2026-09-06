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
  * @内  容  机器人轮子PID速度控制
  * 
  ******************************************************************************
  */

/* Includes ------------------------------------------------------------------*/
#include "ax_speed.h"
#include "ax_robot.h"

int16_t motor_pwm_out[4] = {0};

/**
  * @简  述  电机PID控制函数
  * @参  数  spd_target:编码器速度目标值 ,范围（±250）
  *          spd_current: 编码器速度当前值
  * @返回值  电机PWM速度
  */
int16_t AX_SPEED_PidCtlA(float spd_target, float spd_current)
{
	//static int16_t motor_pwm_out;
	static float bias,bias_last;

	//获得偏差值
	bias = spd_target - spd_current;
	
	//PID计算电机输出PWM值
	motor_pwm_out[0] += ax_motor_kp*bias + ax_motor_kd*(bias-bias_last);
	
	//记录上次偏差
	bias_last = bias;
	
	//返回PWM控制值
	return motor_pwm_out[0];
}	

/**
  * @简  述  电机PID控制函数
  * @参  数  spd_target:编码器速度目标值 
  *          spd_target: 编码器速度当前值
  * @返回值  电机PWM速度
  */
int16_t AX_SPEED_PidCtlB(float spd_target, float spd_current)
{
	//static int16_t motor_pwm_out;
	static float bias,bias_last;

	//获得偏差值
	bias = spd_target - spd_current;
	
	//PID计算电机输出PWM值
	motor_pwm_out[1] += ax_motor_kp*bias + ax_motor_kd*(bias-bias_last);
	
	//记录上次偏差
	bias_last = bias;
	
	//返回PWM控制值
	return motor_pwm_out[1];
}

/**
  * @简  述  电机PID控制函数
  * @参  数  spd_target:编码器速度目标值 
  *          spd_target: 编码器速度当前值
  * @返回值  电机PWM速度
  */
int16_t AX_SPEED_PidCtlC(float spd_target, float spd_current)
{
	//static int16_t motor_pwm_out;
	static float bias,bias_last;

	//获得偏差值
	bias = spd_target - spd_current;
	
	//PID计算电机输出PWM值
	motor_pwm_out[2] += ax_motor_kp*bias + ax_motor_kd*(bias-bias_last);
	
	//记录上次偏差
	bias_last = bias;
	
	//返回PWM控制值
	return motor_pwm_out[2];
}

/**
  * @简  述  电机PID控制函数
  * @参  数  spd_target:编码器速度目标值 
  *          spd_target: 编码器速度当前值
  * @返回值  电机PWM速度
  */
int16_t AX_SPEED_PidCtlD(float spd_target, float spd_current)
{
	//static int16_t motor_pwm_out;
	static float bias,bias_last;

	//获得偏差值
	bias = spd_target - spd_current;
	
	//PID计算电机输出PWM值
	motor_pwm_out[3] += ax_motor_kp*bias + ax_motor_kd*(bias-bias_last);
	
	//记录上次偏差
	bias_last = bias;
	
	//返回PWM控制值
	return motor_pwm_out[3];
}


/******************* (C) 版权 2026 XTARK **************************************/

