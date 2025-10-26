FROM arm64v8/ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
SHELL ["/bin/bash", "-lc"]

# 1. Install system dependencies
RUN apt-get update && apt-get install -y \
    locales tzdata gnupg2 ca-certificates lsb-release software-properties-common \
    git wget curl build-essential cmake pkg-config meson ninja-build \
    python3 python3-pip python3-setuptools python3-wheel python3-colcon-common-extensions \
    libgnutls28-dev libssl-dev libexpat1-dev libjpeg-dev libtiff5-dev libpng-dev \
    libdrm-dev libevent-dev libglib2.0-dev libudev-dev udev python3-yaml python3-jinja2 \
    && locale-gen en_US en_US.UTF-8 && update-locale LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8

# 2. Install ROS 2 Humble
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main" \
    > /etc/apt/sources.list.d/ros2.list

RUN apt-get update && apt-get install -y \
    ros-humble-ros-base \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-camera-info-manager \
    ros-humble-rmw-cyclonedds-cpp && \
    rm -rf /var/lib/apt/lists/*

RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

# 3. Build libcamera (Raspberry Pi stable branch)
WORKDIR /opt/src
RUN git clone --branch stable https://github.com/raspberrypi/libcamera.git && \
    cd libcamera && \
    meson setup build \
      -Dprefix=/usr \
      -Dbuildtype=release \
      -Dpipelines=all \
      -Dcam=disabled \
      -Dgstreamer=disabled \
      -Dpycamera=disabled \
      -Ddocumentation=false && \
    ninja -C build -j$(nproc) && \
    ninja -C build install && \
    ldconfig

# 4. Build libcamera_ros
WORKDIR /ros2_ws/src
RUN git clone https://github.com/raspberrypi/libcamera_ros.git

WORKDIR /ros2_ws
RUN source /opt/ros/humble/setup.bash && colcon build --merge-install

RUN echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc

# 5. Set default RMW
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# 6. Launch command
CMD source /opt/ros/humble/setup.bash && \
    source /ros2_ws/install/setup.bash && \
    ros2 launch libcamera_ros libcamera.launch.py \
      camera_info_url:=file:///camera_info.yaml \
      --ros-args -p image_width:=1280 -p image_height:=720 -p framerate:=30
