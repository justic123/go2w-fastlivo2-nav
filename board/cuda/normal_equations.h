// SPDX-License-Identifier: MIT
#pragma once
#include <cstddef>

namespace go2w {
// H is N x 6 column-major; weighted_transpose is 6 x N column-major.
// Outputs are row-major HtWH[36], followed by HtWr[6], all FP64.
class NormalEquationsCUDA {
 public:
  NormalEquationsCUDA();
  ~NormalEquationsCUDA();
  NormalEquationsCUDA(const NormalEquationsCUDA&) = delete;
  NormalEquationsCUDA& operator=(const NormalEquationsCUDA&) = delete;
  void compute(const double* h, const double* weighted_transpose,
               const double* residual, std::size_t count, double* output);
 private:
  struct Impl;
  Impl* impl_;
};
}
