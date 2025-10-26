FROM ros:humble

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-lc"]

# Build alati + ROS ovisnosti + CycloneDDS
RUN apt-get update && apt-get install -y \
    git build-essential cmake pkg-config \
    python3-colcon-common-extensions \
    ros-humble-ros-base \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-camera-info-manager \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Pripremi ROS workspace i kloniraj libcamera_ros
ENV ROS_DISTRO=humble
WORKDIR /ros2_ws/src
RUN git clone https://github.com/raspberrypi/libcamera_ros.git
WORKDIR /ros2_ws

# Putanje za libcamera s hosta (bit će bind-mountano u /usr/local/*)
ENV PKG_CONFIG_PATH=/usr/local/lib/aarch64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Na prvom startu napravi build, potom pokreni driver
CMD source /opt/ros/${ROS_DISTRO}/setup.bash && \
    if [ ! -d /ros2_ws/install ]; then colcon build --merge-install; fi && \
    source /ros2_ws/install/setup.bash && \
    ros2 launch libcamera_ros libcamera.launch.py \
      camera_info_url:=file:///camera_info.yaml \
      --ros-args -p image_width:=1280 -p image_height:=720 -p framerate:=30
