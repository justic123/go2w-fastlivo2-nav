#include <rclcpp/rclcpp.hpp>
#include <unitree_go/msg/low_state.hpp>
#include <chrono>
#include <iostream>
#include <iomanip>
#include <mutex>
#include <string>
std::mutex output_mutex;
void receive(const unitree_go::msg::LowState::SharedPtr msg_ptr) {
  const auto wall = std::chrono::system_clock::now().time_since_epoch();
  const auto mono = std::chrono::steady_clock::now().time_since_epoch();
  const auto& msg = *msg_ptr;
  std::lock_guard<std::mutex> lock(output_mutex);
  std::cout << std::chrono::duration_cast<std::chrono::nanoseconds>(wall).count()
            << ',' << std::chrono::duration_cast<std::chrono::nanoseconds>(mono).count()
            << ',' << msg.tick;
  for (auto v : msg.imu_state.gyroscope) std::cout << ',' << v;
  for (auto v : msg.imu_state.accelerometer) std::cout << ',' << v;
  for (auto v : msg.imu_state.quaternion) std::cout << ',' << v;
  std::cout << std::endl;
}


int main(int argc,char**argv) {
 int seconds = 120;
 try { if (argc > 1) seconds = std::stoi(argv[1]); } catch (...) { return 2; }
 if (seconds < 5 || seconds > 120) return 2;
 rclcpp::init(argc,argv);
 std::cout << std::setprecision(9);
 std::cout << "receive_unix_ns,receive_monotonic_ns,tick,gx,gy,gz,ax,ay,az,qw,qx,qy,qz\n";
 auto node=std::make_shared<rclcpp::Node>("go2w_ros2_imu_source");
 auto sub=node->create_subscription<unitree_go::msg::LowState>("/lowstate",rclcpp::QoS(100).best_effort(),receive);
 rclcpp::executors::SingleThreadedExecutor exec;
 exec.add_node(node);
 auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(seconds);
 while(rclcpp::ok() && std::chrono::steady_clock::now()<deadline) exec.spin_once(std::chrono::milliseconds(100));
 rclcpp::shutdown();
}
