// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>

namespace go2w {
// Match the existing FAST-LIVO2 visual/plane-map insertion convention exactly.
// It stores the normalized coordinate as float, adjusts negatives, then truncates. Do not floor
// first: that shifts negative queries by an extra voxel. Even exact negative
// boundaries retain the legacy convention so plane-map queries stay compatible.
inline std::int64_t mapVoxelIndex(double coordinate, double voxel_size) {
  float scaled = coordinate / voxel_size;
  if (scaled < 0) scaled -= 1.0;
  return static_cast<std::int64_t>(scaled);
}
}
