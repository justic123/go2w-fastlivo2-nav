#include <unitree/robot/go2/video/video_client.hpp>
#include <chrono>
#include <iostream>
#include <thread>
using Clock=std::chrono::steady_clock;
int main(){
 unitree::robot::ChannelFactory::Instance()->Init(0,"eth0");
 unitree::robot::go2::VideoClient c;c.SetTimeout(2.f);c.Init();
 auto begin=Clock::now();std::cout<<"phase,start_mono_ns,end_mono_ns,status,bytes\n";
 for(int phase=0;phase<2;++phase){
  auto first=begin+std::chrono::seconds(phase?40:10),end=first+std::chrono::seconds(20);
  std::this_thread::sleep_until(first);
  while(Clock::now()<end){
   auto a=Clock::now();std::vector<uint8_t> data;int ret=c.GetImageSample(data);auto b=Clock::now();
   std::cout<<(phase?"1hz":"5hz")<<','<<std::chrono::duration_cast<std::chrono::nanoseconds>(a.time_since_epoch()).count()<<','<<std::chrono::duration_cast<std::chrono::nanoseconds>(b.time_since_epoch()).count()<<','<<ret<<','<<data.size()<<std::endl;
   std::this_thread::sleep_until(a+std::chrono::milliseconds(phase?1000:200));
  }
 }
 std::this_thread::sleep_until(begin+std::chrono::seconds(70));
}
