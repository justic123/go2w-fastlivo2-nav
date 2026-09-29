#include <unitree/idl/go2/LowState_.hpp>
#include <unitree/ros2_idl/Imu_.hpp>
#include <iostream>
int main(){unitree_go::msg::dds_::LowState_ m; sensor_msgs::msg::dds_::Imu_ out;
std::cout << "gyro offset " << (char*)m.imu_state().gyroscope().data()-(char*)&m << " acc offset " << (char*)m.imu_state().accelerometer().data()-(char*)&m << "\n";
std::cout << "output gyro offset " << (char*)&out.angular_velocity()-(char*)&out << " acc offset " << (char*)&out.linear_acceleration()-(char*)&out << "\n";}
