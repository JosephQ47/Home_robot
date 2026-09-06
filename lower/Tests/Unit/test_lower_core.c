#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "chassis_task.h"
#include "command_task.h"
#include "crc16.h"
#include "monitor_task.h"
#include "protocol_messages.h"
#include "protocol_parser.h"
#include "protocol_serializer.h"
#include "protocol_validate.h"
static HrFrameView parse_one(const uint8_t *bytes,size_t size,HrProtocolParser *p){HrFrameView f={0};bool found=false;for(size_t i=0;i<size;i++)if(hr_protocol_parser_feed(p,bytes[i],&f))found=true;assert(found);return f;}
int main(void){
    assert(hr_crc16_ccitt_false((const uint8_t *)"123456789",strlen("123456789"))==0x29B1u);
    uint8_t payload[HR_CMD_MOTION_PAYLOAD_SIZE],frame[HR_FRAME_MAX_SIZE];HrCmdMotion motion={100,-200,true};hr_encode_cmd_motion_payload(payload,&motion);
    size_t n=hr_protocol_serialize(HR_MSG_CMD_MOTION,7u,1000u,payload,sizeof(payload),frame,sizeof(frame));assert(n==24u);
    HrProtocolParser parser;hr_protocol_parser_init(&parser);HrFrameView view=parse_one(frame,n,&parser);HrCmdMotion decoded={0};assert(hr_decode_cmd_motion(&view,&decoded)==HR_PROTOCOL_OK);assert(decoded.vx_mm_s==100&&decoded.wz_mrad_s==-200&&decoded.enable);
    assert(hr_validate_command_freshness(8u,7u,true,1020u,1010u,150u)==HR_PROTOCOL_OK);
    assert(hr_validate_command_freshness(7u,7u,true,1000u,1010u,150u)==HR_PROTOCOL_STALE_SEQUENCE);
    assert(hr_validate_command_freshness(8u,7u,true,1200u,1010u,150u)==HR_PROTOCOL_STALE_TIMESTAMP);
    frame[13]^=1u;hr_protocol_parser_init(&parser);HrFrameView ignored={0};bool accepted=false;for(size_t i=0;i<n;i++)accepted|=hr_protocol_parser_feed(&parser,frame[i],&ignored);assert(!accepted&&parser.bad_frames==1u);frame[13]^=1u;
    HrCommandTaskContext command;command_task_init(&command);hr_protocol_parser_init(&parser);view=parse_one(frame,n,&parser);assert(command_task_accept_frame(&command,&view,1010u)==HR_PROTOCOL_OK);
    Safety_State_t safe={.control_enable=true};RemoteCandidate_t remote={0};CommandState_t selected=command_task_step(&command,&safe,&remote,1100u);assert(selected.enable&&selected.source==HR_CONTROL_UPPER);selected=command_task_step(&command,&safe,&remote,1161u);assert(!selected.enable&&selected.vx_mps==0.0f);
    HrMonitorTaskContext monitor;monitor_task_init(&monitor);HrSafetyInputs si={.all_motors_online=true,.imu_valid=true,.command_seen=true,.chassis_seen=true,.imu_seen=true,.heartbeat={1000u,1000u,1000u}};safe=monitor_task_step(&monitor,&si,1020u);assert(safe.control_enable&&safe.watchdog_gate_ok);safe=monitor_task_step(&monitor,&si,1031u);assert(!safe.control_enable&&!safe.watchdog_gate_ok&&safe.latched_faults!=0u);si.heartbeat=(TaskHeartbeat_t){1040u,1040u,1040u};safe=monitor_task_step(&monitor,&si,1041u);assert(!safe.control_enable);si.clear_fault_request=true;safe=monitor_task_step(&monitor,&si,1042u);assert(safe.control_enable&&safe.latched_faults==0u);HrMonitorTaskContext startup;monitor_task_init(&startup);HrSafetyInputs unseen={.all_motors_online=true,.imu_valid=true};safe=monitor_task_step(&startup,&unseen,0u);assert(!safe.control_enable&&!safe.watchdog_gate_ok);
    HrControlArbiter arb;hr_control_arbiter_init(&arb);safe.control_enable=true;remote=(RemoteCandidate_t){.link_valid=true,.takeover=true,.sticks_centered=false,.vx_mps=0.2f,.stamp_ms=1200u};selected=hr_control_arbiter_step(&arb,&safe,&command.upper,&remote,1200u);assert(!selected.enable);remote.sticks_centered=true;selected=hr_control_arbiter_step(&arb,&safe,&command.upper,&remote,1201u);assert(!selected.enable);remote.sticks_centered=false;selected=hr_control_arbiter_step(&arb,&safe,&command.upper,&remote,1202u);assert(selected.source==HR_CONTROL_REMOTE);selected=hr_control_arbiter_step(&arb,&safe,&command.upper,&remote,1301u);assert(!selected.enable);
    HrChassisConfig cc={.track_width_m=0.4f,.max_vx_mps=0.5f,.max_wz_rps=1.0f,.accel_mps2=1.0f,.decel_mps2=2.0f,.configured=true};CommandState_t ccmd={.vx_mps=0.5f,.wz_rps=1.0f,.enable=true,.valid=true};HrWheelTargets wheels;assert(chassis_task_step(&cc,&ccmd,&safe,0.1f,&wheels));assert(fabsf(wheels.left_mps-0.08f)<0.0001f&&fabsf(wheels.right_mps-0.12f)<0.0001f);safe.control_enable=false;assert(chassis_task_step(&cc,&ccmd,&safe,0.1f,&wheels));assert(wheels.left_mps==0.0f&&wheels.right_mps==0.0f&&cc.vx_now==0.0f);
    puts("PASS: protocol, timeout, safety gate, takeover gate, ramp and differential drive");return 0;
}
