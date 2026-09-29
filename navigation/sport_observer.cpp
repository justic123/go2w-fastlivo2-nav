// Read-only feedback recorder. Never constructs SportClient or sends commands.
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>
#include <unitree/idl/go2/SportModeState_.hpp>
#include <json.hpp>
#include <chrono>
#include <thread>
#include <iostream>
#include <atomic>
int main(int argc,char**argv){
 if(argc<2||argc>3)return 2;
 unitree::robot::ChannelFactory::Instance()->Init(0,argv[1]);
 std::atomic<unsigned> count{0};
 unitree::robot::ChannelSubscriber<unitree_go::msg::dds_::SportModeState_> sub(argc==3 ? "rt/sportmodestate" : "rt/lf/sportmodestate");
 sub.InitChannel([&](const void* raw){
  auto m=static_cast<const unitree_go::msg::dds_::SportModeState_*>(raw);
  double t=std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
  std::cout<<nlohmann::json({{"receipt",t},{"position",m->position()},{"velocity",m->velocity()},{"yaw_speed",m->yaw_speed()},{"rpy",m->imu_state().rpy()},{"mode",m->mode()},{"gait_type",m->gait_type()}}).dump()<<std::endl;++count;
 },1);
 std::this_thread::sleep_for(std::chrono::seconds(120));
 return count?0:1;
}
