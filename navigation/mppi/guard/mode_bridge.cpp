// Go2W commissioning/arrival transport. No velocity or posture commands.
#include <unitree/robot/b2/sport/sport_client.hpp>
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>
#include <unitree/idl/go2/SportModeState_.hpp>
#include <json.hpp>
#include <atomic>
#include <mutex>
#include <thread>
#include <chrono>
#include <iostream>
#include <cmath>
#include <signal.h>
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
static volatile sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static double mono(){timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){
 if(argc!=3&&argc!=4)return 2;
 bool observe=std::string(argv[2])=="--observe";
 bool change=std::string(argv[2])=="--switch"&&argc==4&&(std::string(argv[3])=="0"||std::string(argv[3])=="1");
 if(!observe&&!change)return 2;
 signal(SIGTERM,stop);signal(SIGINT,stop);
 int lock=-1;
 if(change){lock=open("/home/unitree/fast_livo2_port/build1/point_trial.lock",O_WRONLY|O_CREAT,0600);if(lock<0||flock(lock,LOCK_EX|LOCK_NB)!=0){std::cerr<<"motion lease busy"<<std::endl;return 3;}}
 unitree::robot::ChannelFactory::Instance()->Init(0,argv[1]);
 std::mutex mutex;nlohmann::json latest;double stable_since=0;unsigned count=0;
 unitree::robot::ChannelSubscriber<unitree_go::msg::dds_::SportModeState_> sub("rt/lf/sportmodestate");
 sub.InitChannel([&](const void* raw){auto m=static_cast<const unitree_go::msg::dds_::SportModeState_*>(raw);double now=mono();std::lock_guard<std::mutex> g(mutex);
 if(latest.empty()||now-latest["received_monotonic"].get<double>()>.25)stable_since=0;
 bool quiet=(m->mode()==1||m->mode()==3)&&std::isfinite(m->velocity()[0])&&std::isfinite(m->velocity()[1])&&std::isfinite(m->yaw_speed())&&std::hypot(m->velocity()[0],m->velocity()[1])<.025&&std::abs(m->yaw_speed())<.025;
 if(!quiet)stable_since=0;else if(!stable_since)stable_since=now;
 latest={{"kind","feedback"},{"gait_type",m->gait_type()},{"sport_mode",m->mode()},{"velocity",m->velocity()},{"yaw_speed",m->yaw_speed()},{"received_monotonic",now},{"sequence",++count}};
 },1);
 auto began=mono();bool sent=false;
 while(!stopped&&mono()-began<(observe?300:8)){
  nlohmann::json row;double stable;
  {std::lock_guard<std::mutex> g(mutex);row=latest;stable=stable_since;}
  if(change&&!sent){
   if(!row.empty()&&mono()-row["received_monotonic"].get<double>()<.2&&stable&&mono()-stable>1.){
    if(stopped)break;
    unitree::robot::b2::SportClient client;client.SetTimeout(1.f);client.Init();
    int code=client.SwitchGait(std::stoi(argv[3]));sent=true;
    std::cout<<nlohmann::json({{"kind","ack"},{"code",code},{"requested_gait",std::stoi(argv[3])},{"issued_monotonic",mono()}}).dump()<<std::endl;
    if(code!=0)return 4;
   }else if(mono()-began>3){std::cout<<nlohmann::json({{"kind","ack"},{"code",-1},{"error","No fresh stationary sport feedback"}}).dump()<<std::endl;return 5;}
  }else if(!row.empty())std::cout<<row.dump()<<std::endl;
  std::this_thread::sleep_for(std::chrono::milliseconds(100));
 }
 return 0;
}
