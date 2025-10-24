# -------- Base with ROS Humble support --------
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV ROS_DISTRO=humble

# --- OS deps ---
RUN apt-get update && apt-get install -y \
    curl gnupg2 lsb-release ca-certificates locales \
    python3 python3-pip python3-opencv python3-yaml v4l-utils \
    && locale-gen en_US en_US.UTF-8 && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# --- ROS 2 Humble apt repo + install ---
RUN apt-get update && apt-get install -y curl gnupg2 lsb-release && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
      | tee /usr/share/keyrings/ros-archive-keyring.gpg > /dev/null && \
    echo "deb [arch=arm64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
      > /etc/apt/sources.list.d/ros2.list && \
    apt-get update && apt-get install -y \
      ros-humble-ros-base \
      ros-humble-cv-bridge \
      ros-humble-image-transport \
    && rm -rf /var/lib/apt/lists/*

# --- env for ROS runtime ---
ENV ROS_ROOT=/opt/ros/${ROS_DISTRO}
ENV PATH=${ROS_ROOT}/bin:${PATH}
ENV LD_LIBRARY_PATH=${ROS_ROOT}/lib:${LD_LIBRARY_PATH}
ENV PYTHONPATH=${ROS_ROOT}/lib/python3.10/site-packages:${PYTHONPATH}

WORKDIR /app

# --- Camera node ---
COPY camera_node.py /app/camera_node.py

# Defaults (override via compose ENV)
ENV CAMERA_DEVICE=/dev/video0 \
    CAMERA_WIDTH=1280 \
    CAMERA_HEIGHT=720 \
    CAMERA_FPS=30 \
    CAMERA_INFO_YAML=/app/camera_info.yaml

# --- Entrypoint: source ROS + run node ---
ENTRYPOINT ["/bin/bash","-lc","source /opt/ros/${ROS_DISTRO}/setup.bash && python3 /app/camera_node.py"]

