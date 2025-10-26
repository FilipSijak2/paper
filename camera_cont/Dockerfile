# Base: Debian Bookworm ARM64 (closest to Raspberry Pi OS)
FROM arm64v8/debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
SHELL ["/bin/bash", "-lc"]

# 1. System setup and tools
RUN apt-get update && apt-get install -y \
    locales tzdata gnupg2 ca-certificates lsb-release \
    git wget curl build-essential cmake pkg-config meson ninja-build \
    python3 python3-pip python3-setuptools python3-wheel python3-colcon-common-extensions \
    libgnutls28-dev libssl-dev libexpat1-dev libjpeg-dev libtiff5-dev libpng-dev \
    libdrm-dev libevent-dev libglib2.0-dev libudev-dev \
    udev && \
    locale-gen en_US en_US.UTF-8 && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8

# 2. Add ROS 2 Humble repo
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg && \
  echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu bookworm main" \
  > /etc/apt/sources.list.d/ros2.list

# 3. Install ROS 2 Humble Base
RUN apt-get update && apt-get install -y \
    ros-humble-ros-base \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-camera-info-manager \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

ENV ROS_DISTRO=humble
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> /root/.bashrc

# 4. Build libcamera (Raspberry Pi stable fork)
WORKDIR /opt/src
RUN git clone --branch stable https://github.com/raspberrypi/libcamera.git && \
    cd libcamera && \
    meson setup build \
      -Dprefix=/usr \
      -Dbuildtype=release \
      -Dpipelines=all \
      -Dtest=false \
      -Ddocumentation=false \
      -Dcam=disabled \
      -Dgstreamer=disabled \
      -Dpycamera=disabled && \
    ninja -C build -j$(nproc) && \
    ninja -C build install && \
    ldconfig

# 5. Build libcamera_ros
WORKDIR /ros2_ws/src
RUN git clone https://github.com/raspberrypi/libcamera_ros.git
WORKDIR /ros2_ws
RUN source /opt/ros/${ROS_DISTRO}/setup.bash && colcon build --merge-install

RUN echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc

# 6. Set RMW
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# 7. Default command (1080p config)
CMD source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source /ros2_ws/install/setup.bash && \
    ros2 launch libcamera_ros libcamera.launch.py camera_info_url:=file:///camera_info.yaml --ros-args -p image_width:=1280 -p image_height:=720 -p framerate:=30
