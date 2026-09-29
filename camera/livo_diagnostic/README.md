# Go2W板端LIVO诊断

该目录在现有独立FAST-LIVO2工作空间接入原装头部图像。JPEG读取→ROS CompressedImage→640×360 BGR Image→FAST-LIVO2视觉模块；XT16和ROS2 LowState沿用已测试桥接。

- `jpeg_source/`：只调用SDK2 GetImageSample，以约5Hz上限请求；发布/go2w_livo/jpeg，ROS时间戳为SDK返回时刻，非曝光时刻。100秒硬上限。
- `decode_jpeg.py`：验证输入1920×1080，缩小到640×360，发布/go2w_livo/image_raw，保存接收/发布/拒绝计数。95秒上限。
- `livo_candidate.yaml`：独立启用视觉，Go2 URDF+官方XT16候选组合；不更改原LIO配置。
- `camera_candidate.yaml`：社区1080p焦距/主点缩小3倍；显式舍弃原文件非标准矩阵项；未经本机标定。k3为0，剩余四个系数符合当前Pinhole加载器。输入不预先去畸变。
- `run_board_livo.sh`：独立ROS master 11321，相机参数加载/go2w_lio/laserMapping；运行5～60秒（实际建议60），结束清理相机、解码、算法、驱动与master。
- `analyze_run.py`：检查图像数、非零视觉检索、里程计和失败情况；execution_pass只代表执行链路通过。

板端构建JPEG源：在干净环境source /opt/ros/noetic/setup.bash，cmake的CMAKE_PREFIX_PATH包括/home/unitree/go2w_slam_setup/sdk2与/opt/ros/noetic；构建目录为build1/camera/livo_jpeg_build。

板端启动：
```bash
env -i HOME=/home/unitree USER=unitree LANG=C.UTF-8 PATH=/usr/bin:/bin \
 timeout -k 5 110 bash --noprofile --norc \
 /home/unitree/fast_livo2_port/build1/camera/livo_diagnostic/run_board_livo.sh \
 new-unique-livo-run end 60 ros2
```

输出目录必须不存在。相机运行包括传感器发现/预热和结束清理窗口，因此图像计数与60秒主桥接窗口不同。桥接截止可能留下末帧待处理，接收帧数不总等于转发数。无运动命令、无自启动。

当前仅诊断：外参、内参、曝光时间和图像—IMU偏移均未验证；SDK返回时间不能证明同步。动态运动建图和定位精度未验收。H264发现记录中本机为/frontvideostream，未发现文献所用/frontvideo/h264；本实现先使用已验证的JPEG读取。
