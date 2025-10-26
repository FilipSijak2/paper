# Use official Debian Bookworm ARM64 (same base as Raspberry Pi OS)
FROM arm64v8/debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

# 1. Update packages and install system dependencies
RUN apt-get update && apt-get install -y \
    wget gnupg2 lsb-release curl git build-essential cmake \
    python3 python3-pip python3-colcon-common-extensions \
    libcamera-apps libcamera0 libcamera-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Set locale
RUN apt-get update && apt-get install -y locales \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8

# 3. Add ROS 2 Humble repository
RUN apt update && apt install -y curl gnupg2 lsb-release
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
     | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg

RUN echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
     > /etc/apt/sources.list.d/ros2.list

# 4. Install ROS 2 Humble Base
RUN apt-get update && apt-get install -y ros-humble-ros-base \
    ros-humble-cv-bridge ros-humble-image-transport \
    ros-humble-camera-info-manager ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# 5. Setup ROS workspace
ENV ROS_DISTRO=humble
WORKDIR /ros2_ws/src

# Clone Rolling libcamera_ros driver
RUN git clone https://github.com/raspberrypi/libcamera_ros.git -b rolling

WORKDIR /ros2_ws
RUN . /opt/ros/humble/setup.sh && colcon build --merge-install

# Auto-source
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc \
 && echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

CMD ["bash", "-c", "source /opt/ros/humble/setup.sh && source /ros2_ws/install/setup.sh && ros2 launch libcamera_ros libcamera.launch.py camera_info_url:=file:///camera_info.yaml --ros-args -p image_width:=1280 -p image_height:=720 -p framerate:=30"]

