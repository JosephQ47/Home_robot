/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file            : usb_host.c
  * @version         : v1.0_Cube
  * @brief           : This file implements the USB Host
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2024 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/

#include "usb_host.h"
#include "usbh_core.h"
#include "usbh_hid.h"

#include "ax_gamepad.h"

/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* USER CODE BEGIN PV */
/* Private variables ---------------------------------------------------------*/

/* USER CODE END PV */

/* USER CODE BEGIN PFP */
/* Private function prototypes -----------------------------------------------*/

/* USER CODE END PFP */

/* USB Host core handle declaration */
USBH_HandleTypeDef hUsbHostFS;
ApplicationTypeDef Appli_state = APPLICATION_IDLE;

/*
 * -- Insert your variables declaration here --
 */
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/*
 * user callback declaration
 */
static void USBH_UserProcess(USBH_HandleTypeDef *phost, uint8_t id);

/*
 * -- Insert your external function declaration here --
 */
/* USER CODE BEGIN 1 */

/* USER CODE END 1 */

/**
  * Init USB host library, add supported class and start the library
  * @retval None
  */
void USB_HOST_Init(void)
{

	extern USBH_ClassTypeDef  GamePad_HID_Class;
	extern USBH_ClassTypeDef  GamePad_NonStdHID_Class;
	
	if (USBH_Init(&hUsbHostFS, USBH_UserProcess, HOST_FS) != USBH_OK)
	{
		Error_Handler();	
	}
	
	//注册手柄HID类
	if (USBH_RegisterClass(&hUsbHostFS, &GamePad_HID_Class) != USBH_OK) 
	{
		Error_Handler();
	}
	
	if (USBH_Start(&hUsbHostFS) != USBH_OK)
	{
		Error_Handler();
	}
}

/*
 * user callback definition
 */
static void USBH_UserProcess  (USBH_HandleTypeDef *phost, uint8_t id)
{
  /* USER CODE BEGIN CALL_BACK_1 */
  switch(id)
  {
	  case HOST_USER_SELECT_CONFIGURATION:
	  break;

	  case HOST_USER_DISCONNECTION:
	  Appli_state = APPLICATION_DISCONNECT;
	  break;

	  case HOST_USER_CLASS_ACTIVE:
	  Appli_state = APPLICATION_READY;
	  break;

	  case HOST_USER_CONNECTION:
	  Appli_state = APPLICATION_START;
	  break;

	  default:
	  break;
  }
  /* USER CODE END CALL_BACK_1 */
}

/**
  * @简  述  手柄数据读取后,最终进入此回调函数，数据解码在此函数进行(任务环境)
  * @参  数  HID设备句柄
  * @返回值  无
  */
void USBH_HID_EventCallback(USBH_HandleTypeDef *phost)
{
	//手柄数据解码
	USBH_HID_GAMEPAD_Decode(phost);
}
