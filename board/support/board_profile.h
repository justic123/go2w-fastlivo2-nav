// SPDX-License-Identifier: MIT
#pragma once
#include <chrono>
#include <cstddef>
#include <string>

namespace go2w {
bool profiling();
void add_time(const std::string& name, double seconds);
void set_metric(const std::string& name, double value);
void publish_profile();
class Timing {
 public:
  explicit Timing(const char* name) : name_(profiling() ? name : nullptr), start_(std::chrono::steady_clock::now()) {}
  ~Timing() { if (name_) add_time(name_, std::chrono::duration<double>(std::chrono::steady_clock::now()-start_).count()); }
 private:
  const char* name_;
  std::chrono::steady_clock::time_point start_;
};
// CPU owns the estimator. The CUDA output is diagnostic only in this iteration.
void compare_cuda(const double* h, const double* wh, const double* residual,
                  std::size_t n, const double* cpu_normal, const double* cpu_rhs);
}
