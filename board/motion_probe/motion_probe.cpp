// Read-only: query current controller identity and observe high-level state.
// Never initializes SportClient, selects/releases a mode, or publishes lowcmd.
#include <unitree/robot/b2/motion_switcher/motion_switcher_client.hpp>
#include <unitree/robot/channel/channel_factory.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>
#include <unitree/idl/go2/SportModeState_.hpp>
#include <json.hpp>
#include <chrono>
#include <iostream>
#include <mutex>
#include <thread>

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "Usage: go2w_motion_probe networkInterface\n";
    return 2;
  }
  unitree::robot::ChannelFactory::Instance()->Init(0, argv[1]);
  std::mutex mutex;
  int samples = 0;
  nlohmann::json state;
  unitree::robot::ChannelSubscriber<unitree_go::msg::dds_::SportModeState_>
      subscriber("rt/lf/sportmodestate");
  subscriber.InitChannel([&](const void* raw) {
    const auto& value = *static_cast<const unitree_go::msg::dds_::SportModeState_*>(raw);
    std::lock_guard<std::mutex> lock(mutex);
    ++samples;
    state = {{"mode_raw", value.mode()}, {"gait_type_raw", value.gait_type()},
             {"velocity", value.velocity()}, {"yaw_speed", value.yaw_speed()}};
  }, 1);
  // The official Go2W example uses this b2-namespaced shared switcher client.
  unitree::robot::b2::MotionSwitcherClient switcher;
  switcher.SetTimeout(3.0f);
  switcher.Init();
  std::string form, name;
  const int code = switcher.CheckMode(form, name);
  std::this_thread::sleep_for(std::chrono::seconds(3));
  std::lock_guard<std::mutex> lock(mutex);
  std::cout << nlohmann::json({{"read_only", true}, {"check_mode_code", code},
      {"controller_form", form}, {"controller_name", name},
      {"state_samples", samples}, {"state", state},
      {"note", "Current identity and raw state only; not a list of supported gaits or proof of switch capability."}}).dump() << '\n';
  return code == 0 && samples > 0 ? 0 : 1;
}
