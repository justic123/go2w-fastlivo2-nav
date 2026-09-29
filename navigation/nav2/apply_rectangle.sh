#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/foxy/setup.bash
export ROS_DOMAIN_ID=78 ROS_LOCALHOST_ONLY=1
ros2 lifecycle set /controller_server deactivate
ros2 lifecycle set /controller_server cleanup
ros2 param set /controller_server FollowPath.critics '["RotateToGoal", "Oscillation", "BaseObstacle", "ObstacleFootprint", "PathAlign", "PathDist", "GoalDist"]'
ros2 param set /controller_server FollowPath.ObstacleFootprint.scale 1.0
ros2 param set /global_costmap/global_costmap footprint '[[0.375,0.22],[0.375,-0.22],[-0.375,-0.22],[-0.375,0.22]]'
ros2 param set /local_costmap/local_costmap footprint '[[0.375,0.22],[0.375,-0.22],[-0.375,-0.22],[-0.375,0.22]]'
ros2 lifecycle set /controller_server configure
ros2 lifecycle set /controller_server activate
