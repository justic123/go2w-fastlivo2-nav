// Native ROS1 forwarding of ordered ROS2 CSV samples; no motion or cloud code.
#include <ros/ros.h>
#include <sensor_msgs/Imu.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <sstream>
#include <vector>
static volatile sig_atomic_t stopping=0;
static void stop(int){stopping=1;}
static double wall(){return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();}
static double mono(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
int main(int argc,char**argv){
 if(argc!=2)return 2;
 std::string out=argv[1];ros::init(argc,argv,"go2w_imu_forward_native",ros::init_options::NoSigintHandler);
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 ros::NodeHandle node;auto pub=node.advertise<sensor_msgs::Imu>("/go2w_lio/imu",1000);
 std::ofstream timing(out+"/imu_timing.csv"),events(out+"/imu_forward_timing.jsonl");
 timing<<"wall_ns,mono_ns,tick\n";events<<std::setprecision(17);
 std::string line,failure;std::vector<double> anchors;double anchor=0,last_metrics=0,max_residual=0,max_reader=0,max_publish=0;
 unsigned long long first=0,previous=0,duplicates=0,count=0;bool have_tick=false,anchored=false;
 std::getline(std::cin,line); // CSV schema is emitted by our fixed ROS2 source.
 while(!stopping && ros::ok() && std::getline(std::cin,line)){
  const double entered=wall();unsigned long long unix_ns,mono_ns,tick;double gx,gy,gz,ax,ay,az;
  if(std::sscanf(line.c_str(),"%llu,%llu,%llu,%lf,%lf,%lf,%lf,%lf,%lf",&unix_ns,&mono_ns,&tick,&gx,&gy,&gz,&ax,&ay,&az)!=9){failure="Malformed IMU CSV";break;}
  timing<<unix_ns<<','<<mono_ns<<','<<tick<<'\n';
  if(!std::isfinite(gx)||!std::isfinite(gy)||!std::isfinite(gz)||!std::isfinite(ax)||!std::isfinite(ay)||!std::isfinite(az)){failure="Nonfinite IMU";break;}
  if(have_tick && tick==previous){++duplicates;continue;}
  if(have_tick && tick<previous){failure="Tick reset/wrap: stop and reinitialize explicitly";break;}
  if(!have_tick){first=tick;have_tick=true;}previous=tick;
  const double receipt=unix_ns*1e-9,relative=(tick-first)*.001;
  if(!anchored){anchors.push_back(receipt-relative);if(anchors.size()<500)continue;std::sort(anchors.begin(),anchors.end());anchor=(anchors[249]+anchors[250])*.5;anchored=true;}
  const double stamp=anchor+relative,residual=(receipt-stamp)*1000;
  if(std::abs(residual)>500){failure="Tick/host alignment exceeds 500ms guard";break;}
  sensor_msgs::Imu m;m.header.stamp.fromSec(stamp);m.header.frame_id="body_imu_candidate";m.orientation_covariance[0]=-1;
  m.angular_velocity.x=gx;m.angular_velocity.y=gy;m.angular_velocity.z=gz;m.linear_acceleration.x=ax;m.linear_acceleration.y=ay;m.linear_acceleration.z=az;
  const double before=mono();pub.publish(m);const double elapsed=mono()-before;++count;
  max_residual=std::max(max_residual,residual);max_reader=std::max(max_reader,entered-receipt);max_publish=std::max(max_publish,elapsed);
  if(mono()-last_metrics>.5){
   std::ostringstream j;j<<std::setprecision(17)<<"{\"updated\":"<<wall()<<",\"stamp\":"<<stamp<<",\"source_to_reader_s\":"<<entered-receipt<<",\"publish_s\":"<<elapsed<<",\"source_age_s\":"<<wall()-stamp<<",\"imu_published\":"<<count<<",\"max_receipt_tick_residual_ms\":"<<max_residual<<",\"max_source_to_reader_s\":"<<max_reader<<",\"max_publish_s\":"<<max_publish<<"}";
   events<<j.str()<<std::endl;{std::ofstream f(out+"/imu_health.tmp");f<<j.str();}std::rename((out+"/imu_health.tmp").c_str(),(out+"/imu_health.json").c_str());last_metrics=mono();
  }
 }
 if(!stopping && ros::ok() && failure.empty())failure="IMU source ended unexpectedly";
 std::ofstream summary(out+"/imu_summary.json");summary<<std::setprecision(17)<<"{\"imu_published\":"<<count<<",\"duplicate_ticks_dropped\":"<<duplicates<<",\"tick_anchor\":"<<(anchored?std::to_string(anchor):"null")<<",\"max_receipt_tick_residual_ms\":"<<max_residual<<",\"max_source_to_reader_s\":"<<max_reader<<",\"max_publish_s\":"<<max_publish<<",\"failure\":"<<(failure.empty()?"null":"\""+failure+"\"")<<"}";
 ros::shutdown();return failure.empty()?0:1;
}
