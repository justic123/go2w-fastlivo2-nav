// SPDX-License-Identifier: MIT
#include "board_profile.h"
#include "normal_equations.h"
#include <ros/ros.h>
#include <std_msgs/String.h>
#include <map>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <memory>
#include <sstream>
#include <stdexcept>

namespace go2w {
namespace {
std::map<std::string, double> times, metrics;
const std::string& backend() {
  static const std::string value = [] {
    const char* raw = std::getenv("GO2W_CUDA_BACKEND");
    std::string v = raw ? raw : "cpu";
    if (v != "cpu" && v != "shadow") throw std::runtime_error("GO2W_CUDA_BACKEND must be cpu or shadow");
    return v;
  }();
  return value;
}
void json_number(std::ostream& out, double value) {
  if (std::isfinite(value)) out << value;
  else out << "null";
}
}
bool profiling() {
  static const bool enabled = [] { const char* p=std::getenv("GO2W_PROFILE"); return p && std::string(p)=="1"; }();
  return enabled;
}
void add_time(const std::string& name, double seconds) { if (profiling()) times[name] += seconds*1000.; }
void set_metric(const std::string& name, double value) { if (profiling()) metrics[name] = value; }
void publish_profile() {
  if (!profiling()) return;
  static ros::NodeHandle node;
  static ros::Publisher pub=node.advertise<std_msgs::String>("/go2w_lio/profile", 50);
  static unsigned long long sequence=0;
  std::ostringstream out;
  out << std::setprecision(17) << "{\"schema\":1,\"sequence\":" << ++sequence
      << ",\"backend\":\"" << backend() << "\",\"source_clock\":";
  json_number(out, ros::Time::now().toSec());
  for (const auto& group : {std::make_pair("stage_ms", &times), std::make_pair("metrics", &metrics)}) {
    out << ",\"" << group.first << "\":{";
    bool first=true;
    for (const auto& item : *group.second) {
      if (!first) out << ',';
      first=false; out << '"' << item.first << "\":"; json_number(out,item.second);
    }
    out << '}';
  }
  out << '}';
  std_msgs::String msg; msg.data=out.str(); pub.publish(msg);
  times.clear(); metrics.clear();
}
void compare_cuda(const double* h, const double* wh, const double* residual,
                  std::size_t n, const double* cpu_normal, const double* cpu_rhs) {
  if (backend()=="cpu") return;
#ifdef GO2W_HAVE_CUDA
  // The same immutable observations produced the CPU and GPU accumulations.
  // Measure allocation/copies/kernel/sync together, including first-use initialization.
  Timing timer("lio_cuda_total");
  static NormalEquationsCUDA gpu;
  double result[42];
  gpu.compute(h,wh,residual,n,result);
  double max_error=0., max_scaled=0.;
  bool good=true;
  for (int k=0;k<42;++k) {
    const double expected=k<36?cpu_normal[(k%6)*6+k/6]:cpu_rhs[k-36];
    const double error=std::abs(result[k]-expected);
    // Diagnostic acceptance criterion, not a navigation accuracy guarantee.
    const double bound=1e-8+1e-10*std::abs(expected);
    good = good && std::isfinite(result[k]) && std::isfinite(expected) && error<=bound;
    max_error=std::max(max_error,error); max_scaled=std::max(max_scaled,error/bound);
  }
  if (profiling()) {
    metrics["cuda_calls"] += 1;
    metrics["cuda_observations"] = std::max(metrics["cuda_observations"],static_cast<double>(n));
    metrics["cuda_max_abs_error"] = std::max(metrics["cuda_max_abs_error"],max_error);
    metrics["cuda_max_bound_ratio"] = std::max(metrics["cuda_max_bound_ratio"],max_scaled);
  }
  set_metric("cuda_match",good?1:0);
  if (!good) { publish_profile(); throw std::runtime_error("CUDA shadow mismatch; estimator not updated from GPU"); }
#else
  throw std::runtime_error("CUDA shadow requested but this build has no CUDA backend");
#endif
}
}
