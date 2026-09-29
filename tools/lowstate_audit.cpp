// Subscription-only audit: no publisher, client, or motion commands.
#include <unitree/robot/channel/channel_subscriber.hpp>
#include <unitree/idl/go2/LowState_.hpp>
#include <chrono>
#include <thread>
#include <iostream>
#include <iomanip>
#include <mutex>
#include <string>

std::mutex output_mutex;
void receive(const void* data) {
  const auto wall = std::chrono::system_clock::now().time_since_epoch();
  const auto mono = std::chrono::steady_clock::now().time_since_epoch();
  const auto& msg = *static_cast<const unitree_go::msg::dds_::LowState_*>(data);
  std::lock_guard<std::mutex> lock(output_mutex);
  std::cout << std::chrono::duration_cast<std::chrono::nanoseconds>(wall).count()
            << ',' << std::chrono::duration_cast<std::chrono::nanoseconds>(mono).count()
            << ',' << msg.tick();
  for (auto v : msg.imu_state().gyroscope()) std::cout << ',' << v;
  for (auto v : msg.imu_state().accelerometer()) std::cout << ',' << v;
  for (auto v : msg.imu_state().quaternion()) std::cout << ',' << v;
  std::cout << '\n';
}

int main(int argc, char** argv) {
  int seconds = 15;
  try {
    if (argc > 2) return 2;
    if (argc == 2) {
      std::size_t used = 0;
      seconds = std::stoi(argv[1], &used);
      if (used != std::string(argv[1]).size() || seconds < 1 || seconds > 120) return 2;
    }
  } catch (...) { return 2; }
  std::cout << std::setprecision(9);
  std::cout << "receive_unix_ns,receive_monotonic_ns,tick,gx,gy,gz,ax,ay,az,qw,qx,qy,qz\n";
  unitree::robot::ChannelFactory::Instance()->Init(0, "eth0");
  unitree::robot::ChannelSubscriber<unitree_go::msg::dds_::LowState_> sub("rt/lowstate");
  sub.InitChannel(receive, 100);
  std::this_thread::sleep_for(std::chrono::seconds(seconds));
  sub.CloseChannel();
  return 0;
}
