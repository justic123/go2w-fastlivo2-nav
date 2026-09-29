#include "preprocess.h"
#include <cmath>
#include <iostream>

int main()
{
  ros::Time::init();
  Preprocess pre;
  pre.set(false, XT32, 0.1, 1);
  pre.blind_sqr = 0.01;
  pre.N_SCANS = 16;
  PointCloudXYZI::Ptr result(new PointCloudXYZI);
  sensor_msgs::PointCloud2::Ptr msg(new sensor_msgs::PointCloud2);
  pre.process(msg, result);
  if (!result->empty()) return 1;

  pcl::PointCloud<xt32_ros::Point> cloud;
  xt32_ros::Point point{};
  point.x = 2; point.y = 1; point.z = 0; point.intensity = 20;
  point.ring = 0; point.timestamp = 100;
  cloud.push_back(point);
  point.ring = 15; point.timestamp = 100.1;
  cloud.push_back(point);
  pcl::toROSMsg(cloud, *msg);
  pre.process(msg, result);
  if (result->size() != 2 || std::abs(result->back().curvature - 100) > 0.001) return 2;

  auto valid = *msg;
  for (auto& f : msg->fields) if (f.name == "timestamp") f.name = "time";
  pre.process(msg, result);
  if (!result->empty()) return 3;
  *msg = valid;
  for (auto& f : msg->fields) if (f.name == "timestamp") f.datatype = sensor_msgs::PointField::FLOAT32;
  pre.process(msg, result);
  if (!result->empty()) return 4;
  *msg = valid;
  msg->data.resize(1);
  pre.process(msg, result);
  if (!result->empty()) return 5;
  std::cout << "PASS: empty, valid seconds-to-ms, missing timestamp, wrong type, truncated payload\n";
}
