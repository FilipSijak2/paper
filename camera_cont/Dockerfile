FROM ros:rolling-ros-base-noble

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-lc"]

# 1) Build alati + ROS ovisnosti (Rolling)
RUN apt-get update && apt-get install -y \
    git build-essential cmake pkg-config \
    python3-colcon-common-extensions \
    ros-rolling-cv-bridge \
    ros-rolling-image-transport \
    ros-rolling-camera-info-manager \
    ros-rolling-rmw-cyclonedds-cpp \
    # runtime tracing lib (česti rclcpp dependency)
    liblttng-ust1 liblttng-ust-dev \
    # korisne image libovi za camera_ros
    libjpeg-dev libpng-dev libtiff-dev \
    && rm -rf /var/lib/apt/lists/*

ENV ROS_DISTRO=rolling

# 2) Workspace i source
WORKDIR /ros2_ws/src
RUN git clone --depth 1 https://github.com/christianrauch/camera_ros.git

# 3) Natrag u ws root
WORKDIR /ros2_ws

# 4) Libcamera iz hosta: pkg-config + linker putanje (bit će bind-mountano)
ENV PKG_CONFIG_PATH=/usr/local/lib/aarch64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# 5) Build na runtime (kad je host libcamera već montan), pa launch
CMD source /opt/ros/${ROS_DISTRO}/setup.bash && \
    if [ ! -d /ros2_ws/install ]; then colcon build --merge-install; fi && \
    source /ros2_ws/install/setup.bash && \
    ros2 run camera_ros camera_node --ros-args --params-file /camera_params.yaml




