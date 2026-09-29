# RealSense图像接入准备

更新：已通过宇树SDK2网络视频接口取得5张1920×1080图像，详见[实测记录](宇树视频接口实测_2026-09-27.md)。本地USB未识别到相机不代表机器人没有图像来源；RealSense路径仍只作备用准备。

2026-09-27板端检查：已安装ros-noetic-librealsense2 2.50.0、realsense2-camera 2.3.2；USB仅根集线器，没有/dev/video设备。本机USB也未识别到RealSense。因此尚未验证相机型号、图像、相机内参或帧率。

`realsense_color.launch`根据板端已安装的rs_camera.launch参数准备，目标ROS1 Noetic，输出`/go2w_realsense/color/image_raw`和`/go2w_realsense/color/camera_info`。640×480@30只是初始请求，必须在设备连通后确认支持；只打开RGB。未启动相机、未开启算法视觉开关。

应与FAST-LIVO2使用同一ROS master（现有测试为http://127.0.0.1:11321）。相机接入后先保存图像/CameraInfo，确认实际分辨率、畸变模型、时间戳与丢帧，再生成匹配的FAST-LIVO2相机配置。不能把CameraInfo当成雷达到相机的外参；Rcl/Pcl需独立获得并确认变换方向。RGB、IR所需标定分别对应其光学坐标系，不可混用。

官方ROS1文档：https://dev.realsenseai.com/docs/ros1-wrapper/
