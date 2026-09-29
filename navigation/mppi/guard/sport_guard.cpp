#include <unitree/robot/go2/sport/sport_client.hpp>
#include <unitree/robot/channel/channel_factory.hpp>
#include <json.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>
#include <unitree/idl/go2/SportModeState_.hpp>
#include <atomic>
#include <thread>
#include <chrono>
#include <poll.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <cmath>
#include <memory>
#include <iostream>
#include <string>
static volatile sig_atomic_t stop_flag=0;
void stop_signal(int){stop_flag=1;}
double mono(){timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char**argv){
 bool preview_mppi=argc==3 && std::string(argv[2])=="--preview-mppi";
 bool mppi=preview_mppi || (argc==3 && std::string(argv[2])=="--execute-mppi");
 bool preview_floor=argc==3 && std::string(argv[2])=="--preview-floor";
 bool floor=preview_floor || (argc==3 && std::string(argv[2])=="--execute-floor");
 bool preview_nav=argc==3 && std::string(argv[2])=="--preview-nav";
 bool nav=preview_nav || (argc==3 && std::string(argv[2])=="--execute-nav");
 bool preview_point=argc==3 && std::string(argv[2])=="--preview-point";
 bool point=preview_point || (argc==3 && std::string(argv[2])=="--execute-point");
 bool balance=argc==3 && std::string(argv[2])=="--balance";
 bool probe=argc==3 && std::string(argv[2])=="--probe";
 bool preview_startup=argc==3 && std::string(argv[2])=="--preview-startup";
 bool startup=preview_startup || (argc==3 && std::string(argv[2])=="--execute-startup");
 bool execute=(mppi&&!preview_mppi) || (floor&&!preview_floor) || (nav&&!preview_nav) || (point&&!preview_point) || (startup&&!preview_startup) || (argc==3 && std::string(argv[2])=="--execute");
 if(argc<2||argc>3||(argc==3&&!execute&&!probe&&!balance&&!preview_startup&&!preview_point&&!preview_nav&&!preview_floor&&!preview_mppi))return 2;
 signal(SIGINT,stop_signal);signal(SIGTERM,stop_signal);
 std::unique_ptr<unitree::robot::go2::SportClient> client;
 if(execute||probe||balance)unitree::robot::ChannelFactory::Instance()->Init(0,argv[1]);
 if(execute||balance){client.reset(new unitree::robot::go2::SportClient());client->SetTimeout(.15f);client->Init();}
 if(balance){client->SetTimeout(2.f);std::this_thread::sleep_for(std::chrono::seconds(1));int code=client->BalanceStand();std::cout<<nlohmann::json({{"action","BalanceStand"},{"code",code}}).dump()<<std::endl;return code==0?0:1;}
 if(probe){std::atomic<int> count{0};unitree::robot::ChannelSubscriber<unitree_go::msg::dds_::SportModeState_> sub("rt/lf/sportmodestate");sub.InitChannel([&](const void* raw){auto m=static_cast<const unitree_go::msg::dds_::SportModeState_*>(raw);if(count++==0)std::cout<<nlohmann::json({{"mode",m->mode()},{"gait_type",m->gait_type()},{"velocity",m->velocity()},{"yaw_speed",m->yaw_speed()}}).dump()<<std::endl;},1);std::this_thread::sleep_for(std::chrono::seconds(5));std::cout<<nlohmann::json({{"received",count.load()},{"read_only",true}}).dump()<<std::endl;return count>0?0:1;}
 // 独立停车上限：点到点8.5秒；上层8秒退出。断流0.3秒停车，不允许自动重试。
 const double start=mono();double last=start;bool active=false;std::string pending,reason="timeout";int result=0;
 std::cout<<"{\"ready\":true,\"execute\":"<<(execute?"true":"false")<<"}"<<std::endl;
 while(!stop_flag && mono()-start<(mppi?125:floor?1805:nav?65:startup?2.5:point?8.5:20)){
  pollfd p{STDIN_FILENO,POLLIN,0};int status=poll(&p,1,40);
  if(status<0){reason="poll_error";break;}
  if(status>0 && (p.revents&(POLLIN|POLLHUP))){
   char buf[512];int n=read(STDIN_FILENO,buf,sizeof(buf));if(n<=0){reason="stdin_closed";break;}pending.append(buf,n);
   if(pending.size()>4096){reason="oversized_input";break;}
   size_t pos;
   while((pos=pending.find('\n'))!=std::string::npos){
    std::string line=pending.substr(0,pos);pending.erase(0,pos+1);
    try{
     auto j=nlohmann::json::parse(line);double age=mono()-j.at("sent_monotonic").get<double>();
     double vx=j.at("vx"),vy=j.at("vy"),w=j.at("yaw_rate");
     if(!std::isfinite(age)||age<0||age>.15||!std::isfinite(vx)||!std::isfinite(vy)||!std::isfinite(w)||vx<(mppi?-.1:0)||vx>((mppi||floor)?.2:(nav||startup||point)?.1:.06)||vy!=0||std::abs(w)>((mppi||floor||nav)?.8:.12)){std::cout<<nlohmann::json({{"rejected",true},{"command_age_s",age},{"vx",vx},{"vy",vy},{"yaw_rate",w},{"reason","invalid_or_expired_command"}}).dump()<<std::endl;throw std::runtime_error("invalid_or_expired_command");}
     last=mono();active=true;int code=execute?client->Move(vx,0,w):0;
     std::cout<<nlohmann::json({{"code",code},{"execute",execute},{"vx",vx},{"yaw_rate",w}}).dump()<<std::endl;
     if(code!=0){reason="rpc_failed";result=1;stop_flag=1;break;}
    }catch(const std::exception&e){reason=e.what();result=1;stop_flag=1;break;}
   }
  }
  if(mono()-last>(active?.3:3.)){reason="input_watchdog";break;}
 }
 if(stop_flag && reason=="timeout")reason="signal";
 int stop_code=execute?client->StopMove():0;
 std::cout<<nlohmann::json({{"stopped",true},{"reason",reason},{"stop_code",stop_code},{"execute",execute}}).dump()<<std::endl;
 return result || stop_code!=0;
}
