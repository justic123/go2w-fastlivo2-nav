# License scope and third-party notices

The root [MIT license](LICENSE) applies to original project integration code and documentation only. It does **not** replace third-party notices, relicense upstream source or grant rights to Unitree firmware, proprietary binaries, trademarks or datasets. Files with their own notices retain those notices. Upstream-derived patches remain subject to the corresponding upstream license.

This is a source integration repository. External dependencies are fetched separately; a root MIT license is not a statement that a combined executable, container or robot firmware is MIT-licensed. Review the exact component licenses before redistributing binaries, in particular FAST-LIVO2's GPLv2 license and Vikit's GPLv3 declarations. We do not distribute prebuilt combined binaries or promise that all upstream license combinations permit binary redistribution.

## Included source and reference files

| Repository content | Origin and attribution | Applicable notice |
| --- | --- | --- |
| `desktop/ws/src/vikit_common/`, `desktop/ws/src/vikit_ros/` | [xuankuzcr/rpg_vikit](https://github.com/xuankuzcr/rpg_vikit/tree/6c886c8e5d83997806e00294826d528cea3581dd), based on UZH RPG Vikit; Christian Forster and upstream contributors. Some files retain Christian Kerl/dvo notices. | Packages declare GPLv3; preserve individual file notices, including GPLv3-or-later where stated. [GPLv3 text](LICENSES/GPL-3.0.txt), also included as `COPYING` in each package. |
| `FAST-LIVO2-changes.patch`, `dependencies/*FAST-LIVO2.patch`, corresponding `dependencies/extras/*FAST-LIVO2/` tests | [hku-mars/FAST-LIVO2](https://github.com/hku-mars/FAST-LIVO2/tree/0d2c0346107b75b59934975adec9a6eeeb913c64), HKU MARS and upstream authors | [Upstream GPLv2 text](LICENSES/GPL-2.0.txt); patches are not relicensed by root MIT. |
| `Sophus-changes.patch`, `dependencies/*Sophus.patch` | [strasdat/Sophus](https://github.com/strasdat/Sophus/tree/a621ff2e56c56c839a6c40418d42c3c254424b5c), Hauke Strasdat | [MIT header notice](LICENSES/Sophus-MIT.txt) from the pinned source. |
| `dependencies/*livox_ros_driver.patch` | [Livox-SDK/livox_ros_driver](https://github.com/Livox-SDK/livox_ros_driver/tree/3d240d5666129e1a3052e78ee8487a04b08fdda3) | [Upstream MIT and bundled third-party notices](LICENSES/Livox-NOTICES.txt). |
| `camera/parameter-reference/Go2Py_*` | [machines-in-motion/Go2Py](https://github.com/machines-in-motion/Go2Py/tree/eff240b82b0ff6dae6ba5ee934a381f38fe64c0d), Copyright 2023 Rooholla-KhorramBakht | [MIT](LICENSES/Go2Py-MIT.txt). |
| `camera/parameter-reference/dimos_*` | [dimensionalOS/dimos](https://github.com/dimensionalOS/dimos/tree/edd7c346b8158a406c915dfe922202dc2d652e21), Copyright 2026 Dimensional Inc.; preserve in-file headers | [Apache-2.0](LICENSES/Apache-2.0.txt). |
| `camera/parameter-reference/community_front_camera_*.yaml` | [abizovnuralem/go2_ros2_sdk](https://github.com/abizovnuralem/go2_ros2_sdk), RoboVerse community | [BSD-2-Clause](LICENSES/Go2-ROS2-SDK-BSD-2-Clause.txt), retrieved 2026-09-30; exact source revision of the historical calibration copies was not recorded. |
| `camera/parameter-reference/official_go2.urdf`, `official_go2w.urdf` | [unitreerobotics/unitree_ros](https://github.com/unitreerobotics/unitree_ros/tree/ccfc6fd8430a17ba3dacef9a1e2faf64ff3b0aee), Unitree Robotics | [BSD-3-Clause](LICENSES/Unitree-ROS-BSD-3-Clause.txt). |
| Unitree SDK API integration and example-derived portions | [unitreerobotics/unitree_sdk2](https://github.com/unitreerobotics/unitree_sdk2/tree/63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36), Unitree Robotics | [BSD-3-Clause](LICENSES/Unitree-SDK2-BSD-3-Clause.txt); vendor libraries retain their own terms. |

`official_recharge_aruco.yaml` contains numerical calibration reference data transcribed from the Go2W vendor SLAM configuration, not a grant to redistribute the vendor software. See [provenance and limitations](camera/原装前置相机参数核查_2026-09-27.md). Such calibration values are reference candidates, not validated calibration for every robot.

## Separately obtained dependencies

Exact URLs, commits, patch checksums and additional test files are listed in [dependencies/sources.json](dependencies/sources.json). Empty patch files contain no upstream source. FAST-LIVO2, Sophus, ROS, Nav2, Open3D, Livox SDK, Hesai SDK and Unitree SDK retain their own licenses. Dependency restoration does not transfer ownership of their code to this project.

Current deployment and modifications are documented in the project history and patch files. Credit the original FAST-LIVO2 and Nav2 projects when presenting algorithmic results; this repository provides Go2W integration, diagnostics and navigation workflow.
