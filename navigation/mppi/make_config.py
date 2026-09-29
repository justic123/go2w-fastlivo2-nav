"""Generate a Humble-only configuration; do not import BotBrain's mixed-version defaults."""
from pathlib import Path
import yaml
root=Path(__file__).resolve().parent
p=yaml.safe_load((root.parent/'nav2/floor.yaml').read_text())
c=p['controller_server']['ros__parameters']
c.clear();c.update(use_sim_time=True, controller_frequency=20.0, odom_topic='/mppi/odom',
 min_x_velocity_threshold=.001,min_y_velocity_threshold=.001,min_theta_velocity_threshold=.001,
 progress_checker_plugin='progress_checker',goal_checker_plugins=['goal_checker'],controller_plugins=['FollowPath'],
 failure_tolerance=.3,
 progress_checker=dict(plugin='nav2_controller::SimpleProgressChecker',required_movement_radius=.05,movement_time_allowance=20.),
 goal_checker=dict(plugin='nav2_controller::SimpleGoalChecker',xy_goal_tolerance=.08,yaw_goal_tolerance=.12,stateful=False))
c['FollowPath']=dict(plugin='nav2_mppi_controller::MPPIController',time_steps=40,model_dt=.05,batch_size=1000,
 iteration_count=1,vx_std=.12,vy_std=.0,wz_std=.3,vx_max=.2,vx_min=-.1,vy_max=0.,wz_max=.8,
 motion_model='DiffDrive',prune_distance=1.7,transform_tolerance=.6,temperature=.3,gamma=.015,
 visualize=False,regenerate_noises=False,
 critics=['ConstraintCritic','CostCritic','GoalCritic','GoalAngleCritic','PathAlignCritic','PathFollowCritic','PathAngleCritic','PreferForwardCritic','VelocityDeadbandCritic'])
f=c['FollowPath']
for name,weight,threshold in [('ConstraintCritic',4.,None),('CostCritic',3.81,None),('GoalCritic',7.,1.4),('GoalAngleCritic',3.,.12),('PathAlignCritic',6.,.5),('PathFollowCritic',5.,1.4),('PathAngleCritic',2.,.12),('PreferForwardCritic',5.,.5)]:
 f[name]=dict(enabled=True,cost_power=1,cost_weight=weight)
 if threshold is not None:f[name]['threshold_to_consider']=threshold
f['CostCritic'].update(consider_footprint=True,collision_cost=1000000.,critical_cost=300.,near_goal_distance=.5,trajectory_point_step=2)
f['PathAlignCritic'].update(offset_from_furthest=10,trajectory_point_step=4,use_path_orientations=False,max_path_occupancy_ratio=.05)
f['PathFollowCritic']['offset_from_furthest']=5
# Keep path heading guidance until terminal yaw alignment becomes active.
f['VelocityDeadbandCritic']=dict(enabled=True,cost_power=1,cost_weight=35.,deadband_velocities=[.08,0.,0.])
f['PathAngleCritic'].update(offset_from_furthest=4,max_angle_to_furthest=1.,mode=0)
for name in ['global_costmap','local_costmap']:
 k=p[name][name]['ros__parameters'];k.update(use_sim_time=True,robot_base_frame='go2w_mppi_base',transform_tolerance=.6)
 k['obstacle_layer']['lidar'].update(topic='/mppi/cloud',obstacle_max_range=8.,raytrace_max_range=9.,obstacle_min_range=0.,raytrace_min_range=0.)
 for old in ['obstacle_range','raytrace_range']:k['obstacle_layer']['lidar'].pop(old,None)
p['global_costmap']['global_costmap']['ros__parameters'].update(width=60,height=60,origin_x=-30.,origin_y=-30.,update_frequency=2.,publish_frequency=1.)
p['local_costmap']['local_costmap']['ros__parameters'].update(update_frequency=10.,publish_frequency=2.)
p['planner_server']['ros__parameters']['use_sim_time']=True
p['lifecycle_manager']['ros__parameters'].update(use_sim_time=True,node_names=['planner_server','controller_server','velocity_smoother','bt_navigator'])
p['velocity_smoother']=dict(ros__parameters=dict(use_sim_time=True,smoothing_frequency=20.,feedback='OPEN_LOOP',
 scale_velocities=False,max_velocity=[.2,0.,.8],min_velocity=[-.1,0.,-.8],max_accel=[.2,0.,.5],max_decel=[-.3,0.,-.5],
 odom_topic='/mppi/odom',odom_duration=.1,deadband_velocity=[0.,0.,0.],velocity_timeout=.3))
# OPEN_LOOP here estimates the smoother's current output, not navigation position.
p['bt_navigator']=dict(ros__parameters=dict(use_sim_time=True,global_frame='camera_init',robot_base_frame='go2w_mppi_base',odom_topic='/mppi/odom',transform_tolerance=.6,
 default_nav_to_pose_bt_xml='/work/navigate.xml',default_nav_through_poses_bt_xml='/work/navigate_through.xml',bt_loop_duration=10,default_server_timeout=20,
 plugin_lib_names=['nav2_compute_path_through_poses_action_bt_node','nav2_compute_path_to_pose_action_bt_node','nav2_follow_path_action_bt_node','nav2_rate_controller_bt_node','nav2_pipeline_sequence_bt_node']))
if (root/'selection.json').exists():
 import json
 selected=json.loads((root/'selection.json').read_text());mapfile='/work/maps/'+selected['map_id']+'/map.yaml'
 p['map_server']=dict(ros__parameters=dict(use_sim_time=True,yaml_filename=mapfile,topic_name='/map',frame_id='map'))
 g=p['global_costmap']['global_costmap']['ros__parameters'];g['global_frame']='map';g['plugins']=['static_layer','obstacle_layer','inflation_layer'];g['static_layer']=dict(plugin='nav2_costmap_2d::StaticLayer',map_topic='/map',map_subscribe_transient_local=True,subscribe_to_updates=False)
 p['bt_navigator']['ros__parameters']['global_frame']='map'
 p['lifecycle_manager']['ros__parameters']['node_names'].insert(0,'map_server')
# Optional output keeps demo map selection separate from the frozen parameter file.
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=root/'params.yaml');args=parser.parse_args()
 args.output.write_text(yaml.safe_dump(p,sort_keys=False))
