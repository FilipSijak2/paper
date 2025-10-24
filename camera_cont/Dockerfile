# --------- Base Image ---------
FROM ubuntu:24.04

# --------- Environment ---------
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV ROS_DISTRO=humble

# --------- Install dependencies ---------
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-opencv \
    python3-yaml \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

# --------- Workdir ---------
WORKDIR /app

# --------- Copy camera node ---------
COPY camera_node.py /app/camera_node.py

# --------- Entrypoint (source ROS2 from host) ---------
ENTRYPOINT ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 /app/camera_node.py"]
