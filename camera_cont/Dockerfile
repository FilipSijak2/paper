FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-lc"]

# Install dependencies
RUN apt-get update && apt-get install -y \
    git build-essential cmake pkg-config \
    python3-colcon-common-extensions \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-camera-info-manager \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

ENV ROS_DISTRO=humble
WORKDIR /ros2_ws/src

# Clone camera_ros from christianrauch
RUN git clone --depth 1 https://github.com/christianrauch/camera_ros.git

WORKDIR /ros2_ws

ENV PKG_CONFIG_PATH=/usr/local/lib/aarch64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

CMD source /opt/ros/${ROS_DISTRO}/setup.bash && \
    if [ ! -d /ros2_ws/install ]; then colcon build --merge-install; fi && \
    source /ros2_ws/install/setup.bash && \
    ros2 launch camera_ros camera.launch.py \
      camera_info_url:=file:///camera_info.yaml \
      --ros-args \
      -p camera_type:=libcamera \
      -p camera_config:=/camera_info.yaml


