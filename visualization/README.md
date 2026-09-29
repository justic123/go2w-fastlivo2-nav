# Go2W LIVO RViz2可视化

算法在板端ROS1 Noetic运行；本机ROS2 Humble/RViz2用于显示。ros1_view_source.py只订阅输出，通过绑定板端127.0.0.1:11325的TCP服务和SSH隧道发送给本机ros2_view.py。只转发/cloud、里程计和/rgb_img，不转发运动命令。显示采用最新消息覆盖方式，允许丢显示帧；原始建图包独立保存。

本机ROS_DOMAIN_ID=77、ROS_LOCALHOST_ONLY=1，避免显示话题进入机器人DDS域。RViz2配置go2w_livo.rviz：固定坐标camera_init，地图/go2w_view/cloud，轨迹/go2w_view/path，视觉跟踪画面/go2w_view/image。点云按Z着色，可在Color Transformer改RGB8查看彩色点；静态XYZ预览没有RGB字段。

鼠标左键拖动旋转视角，滚轮缩放，中键拖动平移。当前不包含2D目标点工具，尚未接通点到点导航。

本机先在干净终端source /opt/ros/humble/setup.bash，再设置上述domain/localhost变量。启动：
```
python3 /home/river/文档/ChatGPT/巡检/fast_livo2_port/visualization/ros2_view.py
rviz2 -d /home/river/文档/ChatGPT/巡检/fast_livo2_port/visualization/go2w_livo.rviz
```
需要已有SSH隧道：本机127.0.0.1:11325→板端127.0.0.1:11325。板端run_board_mapping_view.sh启动ROS1显示源和最长180秒采集，使用独立延长的相机、IMU读取程序，原60秒入口不变。

点云Decay Time=180秒，仅用于显示累积，不是持久保存；持久地图由rosbag+export_map.py生成。图像和点云使用机器人时间（目前与本机系统时间不同），固定坐标显示不进行时间补偿。ROS2 relay保留来源时间戳；不把显示当成同步验证。

实测调整：初始全量显示转发叠加建图后触发IMU 500ms偏差保护；取消显示的对照运行通过。当前显示源限1Hz、每帧最多约3000点、图像缩小一半；算法本轮滤点间隔8、视觉图像最多2.5Hz，OMP线程上限2、OpenCV解码线程1。500ms时间保护保持有效。完整原因尚未定位，不能仅凭减负成功认定网络或CPU是唯一原因。

## 实时显示闪烁修复（2026-09-27）

livo-live-view-01录包确认/cloud有370帧有效XYZRGB与370帧空帧交替发布。显示源现在在1Hz限流前过滤空帧。本机display_map.py按5厘米体素累积RGB，保留每体素首次颜色，最多30万个体素，达到上限后停止新增并写map_capped状态；这只是可视化缓存，不反馈给算法。RViz使用RGB8、Decay Time=0，每次更新接收完整累计地图。TCP重连重置本轮显示缓存，避免不同初始化坐标系混合。

QT_SCALE_FACTOR=2时截图曾显示整个3D视口黑屏；改为QT_SCALE_FACTOR=1、QT_AUTO_SCREEN_SCALE_FACTOR=0、QT_ENABLE_HIGHDPI_SCALING=0后，小窗和最大化均截图确认网格、RGB点云、图像正常。未据此确诊驱动根因。仍保留1Hz/约3000点每帧限流，避免未经连续性验证就增加板端负担。当前每轮仍限180秒，结束后累计地图保留，数据计数停止；不得当作持续实时运行。

已验证RGB位保持、同体素重复输入不抖动、空帧/NaN不清空地图及语法检查。livo-live-view-02实测map_points从1867增加到2149，计数和时间持续更新。

## 相机预览与彩色地图增密

后续livo-live-view-03解除旧1Hz显示限制：有效点云最多12000点/帧，最短间隔0.35秒；跟踪图同频；已有SDK JPEG流以0.18秒最短间隔转发到电脑，Pillow在电脑解码为640x360 RGB8，发布/go2w_view/camera。没有增加机器人SDK取图请求，也没有增加算法图像输入频率。RViz左侧Live camera (SDK)显示该预览，右侧Live RGB map使用RGB8，点大小5像素。

12秒窗口实测camera=4.92Hz，cloud/image/odom=1.92Hz。地图样本6328点、5027种RGB值，约30.4%点的通道差超过10，确认不是高度伪彩色。原房间多为灰白色；彩色点云不是稠密纹理网格，仅在相机可见区域着色，标定和图像时间仍待精确验证。本机Pillow旧版不支持Resampling枚举，改用兼容BILINEAR后JPEG解码检查与实流通过。

最新入口已取消固定采集时限，参见../持续建图使用说明.md。此前180秒限制仅保留在旧run_livo_static_capture.sh诊断入口；日常请使用../重新采集.sh。

已同时显示VIO tracked features（/go2w_view/image，算法/rgb_img带绿蓝特征圆点，约2Hz）与Live camera (SDK)（/go2w_view/camera，无标记原始预览，约5Hz）。只切换预览不会关闭视觉融合。实流抽帧确认标记存在。
