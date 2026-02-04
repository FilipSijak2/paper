FROM ubuntu:22.04

# Avoid any interactive debconf prompts during image build (e.g., locales).
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
  bash curl jq coreutils \
  ca-certificates gnupg lsb-release locales \
  docker.io iproute2 iputils-ping netcat-openbsd procps util-linux usbutils \
  && rm -rf /var/lib/apt/lists/*

# ROS 2 Humble (Ubuntu 22.04) CLI for ROS graph/topic checks
RUN locale-gen en_US en_US.UTF-8 && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
RUN mkdir -p /etc/apt/keyrings \
  && curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | gpg --dearmor -o /etc/apt/keyrings/ros-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
  > /etc/apt/sources.list.d/ros2.list
RUN apt-get update && apt-get install -y --no-install-recommends \
  ros-humble-ros-base ros-humble-rmw-cyclonedds-cpp python3-argcomplete \
  && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.UTF-8
ENV ROS_DISTRO=humble
ENV ROS_PYTHON_VERSION=3
ENV ROS_VERSION=2
ENV ROS_DOMAIN_ID=0
ENV TZ=Europe/Zagreb

COPY healthcheck.py /usr/local/bin/healthcheck.py
RUN chmod +x /usr/local/bin/healthcheck.py

ENTRYPOINT ["/usr/local/bin/healthcheck.py"]
