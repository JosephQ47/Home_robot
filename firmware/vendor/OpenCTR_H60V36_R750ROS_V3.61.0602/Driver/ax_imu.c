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
  * @说  明
  *
  * 1.三轴加速度传感器、三轴陀螺仪
  * 2.IIC通信采用IO口模拟方式
  *
  ******************************************************************************
  */

#include "ax_imu.h" 
#include "ax_sys.h"
#include "ax_delay.h"

//函数定义
static void IIC_Init(void);
static void IMU_WriteReg(uint8_t reg_address, uint8_t data);
static void IMU_ReadReg(uint8_t reg_address, uint8_t *pdata, uint16_t len);
static uint8_t IIC_Write(uint8_t dev_addr, uint8_t reg_addr, uint8_t len, const uint8_t *data);
static uint8_t IIC_Read(uint8_t dev_addr, uint8_t reg_addr, uint8_t len, uint8_t *data);


/**
  * @简  述  IMU传感器初始化
  * @参  数  无	  
  * @返回值  无
  */
void AX_IMU_Init(void)
{	
	//初始化IIC接口
	IIC_Init();	
	
	//复位IMU
    IMU_WriteReg(REG_RESET,0xB0);  //复位
	AX_Delayus(150000);    //等待传感器稳定
	
	//陀螺仪校准
    IMU_WriteReg(REG_CTRL7,QMI_ACCGYR_DISABLE);      //关闭陀螺仪、加速度计
	IMU_WriteReg(REG_CTRL9,CTRL9_CMD_ONDEMANDCALIVRATION);      //陀螺仪按需校准
	AX_Delayus(2000000);  	//等待传感器稳定
	
	//配置驱动方式
    IMU_WriteReg(REG_CTRL1,0x60);      //配置I2C驱动
	IMU_WriteReg(REG_CTRL7,QMI_ACCGYR_DISABLE);      //关闭陀螺仪、加速度计
	
	//配置IMU参数
    IMU_WriteReg(REG_CTRL7,QMI_ACCGYR_DISABLE);      //关闭陀螺仪、加速度计
	AX_Delayus(2000); 
	
	//配置加速度参数
	AX_IMU_ConfigAcc(ACCRANGE_4G,ACCODR_500HZ,LSPA_MODE_3);
	
	//配置陀螺仪参数
	AX_IMU_ConfigGyro(GYRRANGE_512DPS,GYRODR_500HZ,LSPG_MODE_3);
	
    //使能陀螺仪、加速度计
	IMU_WriteReg(REG_CTRL7,QMI_ACCGYR_ENABLE);      
    AX_Delayus(2000); 
	
}

/**
  * @简  述  配置加速度计参数
  * @参  数  range：量程
  * @参  数  odr：odr输出速率
  * @参  数  mode：低通滤波器模式
  * @返回值  无
  */
void AX_IMU_ConfigAcc(enum QMI_AccRange range, enum QMI_AccOdr odr, enum QMI_LpfMode mode)
{
    unsigned char ctl_dada;

    //设置量程和输出速率，默认自检                                              
    ctl_dada = (unsigned char)range | (unsigned char)odr | 0x80;
	
    IMU_WriteReg(REG_CTRL2, ctl_dada);
	
	//设置低通滤波模式
    IMU_ReadReg(REG_CTRL5, &ctl_dada, 1);
    ctl_dada &= 0xf0;
    ctl_dada |= mode;
    ctl_dada |= 0x01;

    IMU_WriteReg(REG_CTRL5, ctl_dada);
}

/**
  * @简  述  配置陀螺仪参数
  * @参  数  range：量程
  * @参  数  odr：odr输出速率
  * @参  数  mode：低通滤波器模式
  * @返回值  无
  */
void AX_IMU_ConfigGyro(enum QMI_GyrRange range, enum Qmi_GyrOdr odr, enum QMI_LpfMode mode)
{
    unsigned char ctl_dada;
	
	//设置量程和输出速率，默认自检     
    ctl_dada = (unsigned char)range | (unsigned char)odr | 0x80;
    IMU_WriteReg(REG_CTRL3, ctl_dada);

    //设置低通滤波模式
    IMU_ReadReg(REG_CTRL5, &ctl_dada, 1);
    ctl_dada &= 0x0f;
    ctl_dada |= mode;
    ctl_dada |= 0x10;
    IMU_WriteReg(REG_CTRL5, ctl_dada);
}


/**
  * @简  述  获取三轴加速度寄存器输出值
  * @参  数  pbuf：读取的数据缓冲区指针 
  * @返回值  无
  */
void AX_IMU_GetAccData(int16_t *pbuf)
{	
	uint8_t buf[6];
	
	//读取加速度数据
	IMU_ReadReg(REG_AX_L,buf,6);
	
    pbuf[0] = (buf[1] << 8) | buf[0];
    pbuf[1] = (buf[3] << 8) | buf[2];
    pbuf[2] = (buf[5] << 8) | buf[4];	
}

/**
  * @简  述  获取三轴陀螺仪寄存器输出值
  * @参  数  pbuf：读取的数据缓冲区指针 
  * @返回值  无
  */
void AX_IMU_GetGyroData(int16_t *pbuf)
{	
	uint8_t buf[6];
	
	//读取陀螺仪数据
	IMU_ReadReg(REG_GX_L,buf,6);
	
    pbuf[0] = (buf[1] << 8) | buf[0];
    pbuf[1] = (buf[3] << 8) | buf[2];
    pbuf[2] = (buf[5] << 8) | buf[4];	
}


/**
  * @简  述  获取IMU温度传感器寄存器数据
  * @参  数  pbuf：读取的数据缓冲区指针 
  * @返回值  无
  */
void AX_IMU_GetTempData(int16_t *pbuf)
{	
	uint8_t buf[2];

	//读取温度数据
	IMU_ReadReg(REG_TEMPERATURE_L,buf,2);
	
    pbuf[0] = (buf[1] << 8) | buf[0];	
	
	//计算实际温度扩大100倍
	//(((double)tmp/256.0f)*100);	
}


/**
  * @简  述  IMU写寄存器。
  * @参  数  无	  
  * @返回值  无
  */
static void IMU_WriteReg(uint8_t reg_address, uint8_t data)
{
	IIC_Write(QMI8658_ADDR,reg_address,1,&data);
}

/**
  * @简  述  IMU读寄存器。
  * @参  数  无	  
  * @返回值  无
  */
static void IMU_ReadReg(uint8_t reg_address, uint8_t *pdata, uint16_t len)
{
	IIC_Read(QMI8658_ADDR,reg_address,len,pdata);
}


//--------------------------I2C 初始化操作函数-----------------------------------------

/**************************实现函数********************************************
*函数原型:		void IIC_Init(void)
*功　　能:		初始化I2C对应的接口引脚。
*******************************************************************************/
static  void IIC_Init(void)
{			

	GPIO_InitTypeDef  GPIO_InitStructure;

	 RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOB, ENABLE);//使能GPIOB时钟

	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_6 | GPIO_Pin_7;
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_OUT;//普通输出模式
  GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;//推挽输出
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;//100MHz
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;//上拉
  GPIO_Init(GPIOB, &GPIO_InitStructure);//初始化
	
    IIC_SCL=1;
    IIC_SDA=1;
	
}

/**************************实现函数********************************************
*函数原型:		void IIC_Start(void)
*功　　能:		产生IIC起始信号
*******************************************************************************/
static  int IIC_Start(void)
{
	SDA_OUT();     //sda线输出
	IIC_SDA=1;
	if(!READ_SDA)return 0;	
	IIC_SCL=1;
	AX_Delayus(1);
 	IIC_SDA=0;//START:when CLK is high,DATA change form high to low 
	if(READ_SDA)return 0;
	AX_Delayus(1);
	IIC_SCL=0;//钳住I2C总线，准备发送或接收数据 
	return 1;
}

/**************************实现函数********************************************
*函数原型:		void IIC_Stop(void)
*功　　能:	    //产生IIC停止信号
*******************************************************************************/	  
static  void IIC_Stop(void)
{
	SDA_OUT();//sda线输出
	IIC_SCL=0;
	IIC_SDA=0;//STOP:when CLK is high DATA change form low to high
 	AX_Delayus(1);
	IIC_SCL=1; 
	IIC_SDA=1;//发送I2C总线结束信号
	AX_Delayus(1);							   	
}

/**************************实现函数********************************************
*函数原型:		u8 IIC_Wait_Ack(void)
*功　　能:	    等待应答信号到来 
//返回值：1，接收应答失败
//        0，接收应答成功
*******************************************************************************/
static  int IIC_Wait_Ack(void)
{
	u8 ucErrTime=0;
	SDA_IN();      //SDA设置为输入  
	IIC_SDA=1;
	AX_Delayus(1);	   
	IIC_SCL=1;
	AX_Delayus(1);	 
	while(READ_SDA)
	{
		ucErrTime++;
		if(ucErrTime>50)
		{
			IIC_Stop();
			return 0;
		}
	  AX_Delayus(1);
	}
	IIC_SCL=0;//时钟输出0 	   
	return 1;  
} 

/**************************实现函数********************************************
*函数原型:		void IIC_Ack(void)
*功　　能:	    产生ACK应答
*******************************************************************************/
static  void IIC_Ack(void)
{
	IIC_SCL=0;
	SDA_OUT();
	IIC_SDA=0;
	AX_Delayus(1);
	IIC_SCL=1;
	AX_Delayus(1);
	IIC_SCL=0;
}
	
/**************************实现函数********************************************
*函数原型:		void IIC_NAck(void)
*功　　能:	    产生NACK应答
*******************************************************************************/	    
static  void IIC_NAck(void)
{
	IIC_SCL=0;
	SDA_OUT();
	IIC_SDA=1;
	AX_Delayus(1);
	IIC_SCL=1;
	AX_Delayus(1);
	IIC_SCL=0;
}
/**************************实现函数********************************************
*函数原型:		void IIC_Send_Byte(u8 txd)
*功　　能:	    IIC发送一个字节
*******************************************************************************/		  
static  void IIC_Send_Byte(u8 txd)
{                        
    u8 t;   
	SDA_OUT(); 	    
    IIC_SCL=0;//拉低时钟开始数据传输
    for(t=0;t<8;t++)
    {              
        IIC_SDA=(txd&0x80)>>7;
        txd<<=1; 	  
		AX_Delayus(1);   
		IIC_SCL=1;
		AX_Delayus(1); 
		IIC_SCL=0;	
		AX_Delayus(1);
    }	 
} 	 
  
/**************************实现函数********************************************
*函数原型:		u8 IIC_Read_Byte(unsigned char ack)
*功　　能:	    //读1个字节，ack=1时，发送ACK，ack=0，发送nACK 
*******************************************************************************/  
static  u8 IIC_Read_Byte(unsigned char ack)
{
	unsigned char i,receive=0;
	SDA_IN();//SDA设置为输入
    for(i=0;i<8;i++ )
	{
        IIC_SCL=0; 
        AX_Delayus(2);
		IIC_SCL=1;
        receive<<=1;
        if(READ_SDA)receive++;   
		AX_Delayus(2); 
    }					 
    if (ack)
        IIC_Ack(); //发送ACK 
    else
        IIC_NAck();//发送nACK  
    return receive;
}

/**************************实现函数********************************************
*函数原型:		bool i2cWrite(uint8_t addr, uint8_t reg, uint8_t data)
*功　　能:		
*******************************************************************************/
static uint8_t IIC_Write(uint8_t dev_addr, uint8_t reg_addr, uint8_t len, const uint8_t *data)
{
		int i;
    if (!IIC_Start())
        return 1;
    IIC_Send_Byte(dev_addr << 1 );
    if (!IIC_Wait_Ack()) {
        IIC_Stop();
        return 1;
    }
    IIC_Send_Byte(reg_addr);
    IIC_Wait_Ack();
		for (i = 0; i < len; i++) {
        IIC_Send_Byte(data[i]);
        if (!IIC_Wait_Ack()) {
            IIC_Stop();
            return 0;
        }
    }
    IIC_Stop();
    return 0;
}
/**************************实现函数********************************************
*函数原型:		bool i2cWrite(uint8_t addr, uint8_t reg, uint8_t data)
*功　　能:		
*******************************************************************************/
static uint8_t IIC_Read(uint8_t dev_addr, uint8_t reg_addr, uint8_t len, uint8_t *data)
{
    if (!IIC_Start())
        return 1;
    IIC_Send_Byte(dev_addr << 1);
    if (!IIC_Wait_Ack()) {
        IIC_Stop();
        return 1;
    }
    IIC_Send_Byte(reg_addr);
    IIC_Wait_Ack();
    IIC_Start();
    IIC_Send_Byte((dev_addr << 1)+1);
    IIC_Wait_Ack();
    while (len) {
        if (len == 1)
            *data = IIC_Read_Byte(0);
        else
            *data = IIC_Read_Byte(1);
        data++;
        len--;
    }
    IIC_Stop();
    return 0;
}


/******************* (C) 版权 2026 XTARK **************************************/
