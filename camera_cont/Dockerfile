# Base image
FROM ubuntu:24.04

# --- Install system dependencies ---
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-pip \
    python3-opencv \
    libcamera-apps \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    curl \
    gnupg2 \
    lsb-release \
    && curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | apt-key add - \
    && echo "deb [arch=amd64,arm64] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" > /etc/apt/sources.list.d/ros2.list \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y ros-humble-ros-base ros-humble-cv-bridge
WORKDIR /app
COPY camera_publisher.py /app/
CMD ["python3", "/app/camera_publisher.py"]
