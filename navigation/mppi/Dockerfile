FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
COPY ros-archive-keyring.gpg /usr/share/keyrings/ros-archive-keyring.gpg
RUN echo 'deb [signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main' > /etc/apt/sources.list.d/ros2.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends ros-humble-nav2-bringup ros-humble-nav2-mppi-controller ros-humble-nav2-velocity-smoother python3-numpy python3-yaml \
 && rm -rf /var/lib/apt/lists/*
ENV ROS_DOMAIN_ID=79 ROS_LOCALHOST_ONLY=1 HOME=/tmp
WORKDIR /work
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash; exec python3 /work/runtime.py"]
RUN apt-get update -qq && apt-get install -y --no-install-recommends python3-open3d python3-scipy && rm -rf /var/lib/apt/lists/*
