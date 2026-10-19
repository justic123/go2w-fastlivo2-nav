// SPDX-License-Identifier: MIT
#include "normal_equations.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>

int main() {
  go2w::NormalEquationsCUDA gpu;
  std::mt19937 generator(20260930);
  std::normal_distribution<double> random(0.,1.);
  unsigned cases=0;
  for (int n : {0,1,7,255,256,257,1000,8193,16384}) {
    for (double scale : {1e-3,1.,1e3}) {
      std::vector<double> h(6*n),wh(6*n),residual(n);
      for (int i=0;i<n;++i) {
        double weight=0.001+std::abs(random(generator));residual[i]=random(generator)*scale;
        for (int j=0;j<6;++j) { h[j*n+i]=random(generator)*scale;wh[i*6+j]=h[j*n+i]*weight; }
      }
      double output[42],repeat[42];
      gpu.compute(h.data(),wh.data(),residual.data(),n,output);
      gpu.compute(h.data(),wh.data(),residual.data(),n,repeat);
      for (int k=0;k<42;++k) {
        int row=k<36?k/6:k-36,col=k%6;
        long double reference=0;
        for(int i=0;i<n;++i) reference+=(long double)wh[i*6+row]*(k<36?h[col*n+i]:residual[i]);
        if (!std::isfinite(output[k]) || std::abs(output[k]-(double)reference)>1e-8+1e-10*std::abs((double)reference))
          throw std::runtime_error("FP64 reference mismatch");
        if (output[k]!=repeat[k]) throw std::runtime_error("Nonrepeatable output");
      }
      ++cases;
    }
  }
  double output[42];bool rejected=false;
  try { gpu.compute(nullptr,nullptr,nullptr,2000001,output); }
  catch(const std::invalid_argument&) { rejected=true; }
  if(!rejected) throw std::runtime_error("Oversize input not rejected");
  std::cout << "PASS " << cases << " cases, repeated outputs, FP64 references and oversize guard\n";
}
