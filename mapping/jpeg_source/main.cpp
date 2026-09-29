#include <unitree/robot/go2/video/video_client.hpp>
#include <ros/ros.h>
#include <sensor_msgs/CompressedImage.h>
#include <chrono>
#include <thread>
#include <iostream>
int main(int argc,char**argv) {
 ros::init(argc,argv,"go2w_livo_jpeg");ros::NodeHandle nh;
 auto pub=nh.advertise<sensor_msgs::CompressedImage>("/go2w_livo/jpeg",2);
 unitree::robot::ChannelFactory::Instance()->Init(0,"eth0");
 unitree::robot::go2::VideoClient client;client.SetTimeout(2.0f);client.Init();
 ros::NodeHandle private_nh("~");int seconds=240;private_nh.param("duration_sec",seconds,240);if(seconds<0)return 2;
 double rate_hz=5.0;private_nh.param("rate_hz",rate_hz,5.0);if(rate_hz<=0 || rate_hz>30)return 2;
 auto period=std::chrono::microseconds(static_cast<long long>(1000000.0/rate_hz));
 auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(seconds);
 unsigned good=0,bad=0;
 while(ros::ok()&&(seconds==0||std::chrono::steady_clock::now()<deadline)){
  if(!pub.getNumSubscribers()){ros::spinOnce();std::this_thread::sleep_for(std::chrono::milliseconds(50));continue;}
  std::vector<uint8_t> data;auto start=std::chrono::steady_clock::now();int ret=client.GetImageSample(data);
  auto stamp=ros::Time::now();auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
  if(ret==0&&!data.empty()){sensor_msgs::CompressedImage m;m.header.stamp=stamp;m.header.frame_id="head_camera_candidate";m.format="jpeg";m.data=std::move(data);pub.publish(m);++good;}else ++bad;
  std::cout<<"status="<<ret<<" request_ms="<<elapsed<<" good="<<good<<" bad="<<bad<<std::endl;
  ros::spinOnce();std::this_thread::sleep_until(start+period);
 }
}
