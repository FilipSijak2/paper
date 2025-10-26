# Raspberry Pi OS Bookworm ARM64
FROM docker.io/raspberrypi/bookworm:latest

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# 1. Update system
RUN apt-get update && apt-get install -y \
    wget gnupg2 lsb-release curl git build-essential cmake \
    python3 python3-pip python3-colcon-common-extensions \
    libcamera-apps libcamera0 libcamera-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Add ROS 2 Humble repository
RUN apt-get update && apt-get install -y locales \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
    && export LANG=en_US.UTF-8

RUN apt update && apt install -y curl gnupg2 lsb-release
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
     | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg

RUN echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
     > /etc/apt/sources.list.d/ros2.list

# 3. Install ROS 2 Humble Base
RUN apt-get update && apt-get install -y ros-humble-ros-base \
    ros-humble-cv-bridge ros-humble-image-transport \
    ros-humble-camera-info-manager ros-humble-rmw-cyclonedds-cp
