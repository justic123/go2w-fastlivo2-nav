#include <unitree/robot/go2/video/video_client.hpp>
#include <chrono>
#include <fstream>
#include <iostream>
#include <thread>
int main(int argc,char**argv) {
 if(argc!=2)return 2;
 unitree::robot::ChannelFactory::Instance()->Init(0,"eth0");
 unitree::robot::go2::VideoClient client;
 client.SetTimeout(2.0f);client.Init();
 std::this_thread::sleep_for(std::chrono::seconds(2));
 int ok=0;
 for(int i=0;i<5;i++) {
  std::vector<uint8_t> data;
  auto start=std::chrono::steady_clock::now();
  int ret=client.GetImageSample(data);
  auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
  std::cout<<"sample="<<i<<" status="<<ret<<" bytes="<<data.size()<<" request_ms="<<ms<<std::endl;
  if(ret==0&&!data.empty()) {
   std::ofstream f(std::string(argv[1])+"/sample-"+std::to_string(i)+".jpg",std::ios::binary);
   f.write(reinterpret_cast<const char*>(data.data()),data.size());if(f)++ok;
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(500));
 }
 return ok?0:1;
}
