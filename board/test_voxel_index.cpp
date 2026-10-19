// Regression: insertion and retrieval must address the same voxel in every octant.
#include "support/voxel_index.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <map>
#include <tuple>

static long long originalInsertion(double coordinate, double size) {
  float loc = coordinate / size;
  if (loc < 0) loc -= 1.0;
  return static_cast<long long>(loc);
}
int main() {
  for (double size : {0.4, 0.5}) {
    for (int i = -10000; i <= 10000; ++i) {
      const double p = i * 0.000731;
      assert(go2w::mapVoxelIndex(p, size) == originalInsertion(p, size));
    }
    for (int boundary = -10; boundary <= 10; ++boundary) {
      const double p = boundary * size;
      for (double x : {p, std::nextafter(p, -INFINITY), std::nextafter(p, INFINITY)})
        assert(go2w::mapVoxelIndex(x, size) == originalInsertion(x, size));
    }
  }
  using Key = std::tuple<long long,long long,long long>;
  std::map<Key, int> map;
  for (double x : {-0.8, -0.1, 0.1, 0.8})
    for (double y : {-0.8, -0.1, 0.1, 0.8})
      for (double z : {-0.8, -0.1, 0.1, 0.8}) {
        map[{originalInsertion(x,.5),originalInsertion(y,.5),originalInsertion(z,.5)}]=17;
        assert(map.at({go2w::mapVoxelIndex(x,.5),go2w::mapVoxelIndex(y,.5),go2w::mapVoxelIndex(z,.5)})==17);
      }
  // The old lookup (-2) missed the insertion (-1) for a common negative coordinate.
  assert(go2w::mapVoxelIndex(-0.1,.5)==-1);
  assert(static_cast<int>(std::floor(-0.1/.5))-1==-2);
  std::cout << "Voxel index: all octants and negative boundaries passed\n";
}
