FROM ros:noetic-ros-base-focal
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libeigen3-dev libopencv-dev libboost-all-dev ros-noetic-pcl-ros ros-noetic-cv-bridge ros-noetic-image-transport ros-noetic-eigen-conversions python3-numpy python3-opencv python3-pil && rm -rf /var/lib/apt/lists/*
