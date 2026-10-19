"""Publish the newest scan covered by fusion TF; never replay superseded scans."""
def select_cloud(waiting,pose_stamp,now,odom_receipt,expiry=.4,tf_history=None,delivery_wait=0.):
    live=[item for item in waiting if 0<=now-item[2]<=expiry]
    if tf_history is not None:
        # A newer odometry publication must not reset the delivery wait for
        # transforms that already cover an older scan (continuous-pose starvation).
        # TF was published before this selection. ROS MessageFilter handles
        # delivery ordering; an extra wall-time sleep only keeps stale scans
        # active even after their replacement transform has been published.
        settled=[stamp for stamp,sent in tf_history if now-sent>=delivery_wait]
        pose_stamp=min(pose_stamp,max(settled)) if pose_stamp is not None and settled else None
    elif now-odom_receipt<delivery_wait:return None,live
    if pose_stamp is None:return None,live
    covered=[item for item in live if item[1]<=pose_stamp]
    if not covered:return None,live
    chosen=max(covered,key=lambda item:item[1])
    return chosen,[item for item in live if item[1]>chosen[1]]
