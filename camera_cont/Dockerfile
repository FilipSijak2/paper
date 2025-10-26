# Ubuntu 22.04 arm64 (na Pi 5 će povući ARM64 varijantu)
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# 0) OS deps i alatni lanac
RUN apt-get update && apt-get install -y \
    locales tzdata software-properties-common curl wget ca-certificates gnupg2 lsb-release \
    git build-essential cmake pkg-config \
    meson ninja-build \
    python3 python3-pip python3-setuptools python3-wheel python3-yaml python3-jinja2 python3-ply \
    # libcamera build deps
    libgnutls28-dev libssl-dev libexpat1-dev \
    libdrm-dev libevent-dev libjpeg-dev libtiff5-dev libpng-dev libglib2.0-dev libudev-dev \
    # korisno
    udev vim && \
    rm -rf /var/lib/apt/lists/*

# Locale
RUN locale-gen en_US en_US.UTF-8 && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8

# 1) ROS 2 Humble (binarke za Ubuntu 22.04)
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main" \
    > /etc/apt/sources.list.d/ros2.list && \
    apt-get update && apt-get install -y \
      ros-humble-ros-base \
      ros-humble-cv-bridge \
      ros-humble-image-transport \
      ros-humble-camera-info-manager \
      ros-humble-rmw-cyclonedds-cpp && \
    rm -rf /var/lib/apt/lists/*

ENV ROS_DISTRO=humble
SHELL ["/bin/bash", "-lc"]

# 2) Build libcamera (HEAD, sa svim pipelines; headless)
WORKDIR /opt/src
RUN git clone https://git.libcamera.org/libcamera/libcamera.git && \
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

# 3) Build libcamera_ros (main)
WORKDIR /ros2_ws/src
RUN git clone https://github.com/raspberrypi/libcamera_ros.git
WORKDIR /ros2_ws
RUN source /opt/ros/${ROS_DISTRO}/setup.bash && colcon build --merge-install
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> /root/.bashrc && \
    echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc

# 4) DDS
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# 5) Zadana rezolucija 1280x720 @30 (headless), koristi tvoj camera_info.yaml
CMD source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source /ros2_ws/install/setup.bash && \
    ros2 launch libcamera_ros libcamera.launch.py camera_info_url:=file:///camera_info.yaml \
      --ros-args -p image_width:=1280 -p image_height:=720 -p framerate:=30
