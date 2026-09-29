# 限时遥控建图采集

`run_board_mapping.sh`在已验证的LIVO限时启动脚本上增加ROS bag录制。只采集传感器与算法输出，不发送运动指令。最长60秒；操作者收到数据就绪提示后遥控，收到结束提示后停止。

独立run目录保存sensors.bag，包含points、imu、cloud、odometry、jpeg五个话题。rosbag在结束时通过SIGINT完成索引。文件较大，完整bag保留板端。

`export_map.py RUN_DIR`需在板端source ROS Noetic后执行；从/cloud按10cm体素合并XYZ点，导出map_xyz_10cm.pcd、trajectory.tum、mapping_result.json。地图不是原算法内部体素树/导航地图；未生成占据栅格、未验证重定位，也不包含自动回环校正。

估计路径长度与终点位移仅为算法输出。没有操作者实际运动信息或参考真值时，不得当作定位误差。所有相机标定、时间同步仍为LIVO诊断候选。
