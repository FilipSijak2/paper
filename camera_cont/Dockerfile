# ==== Base: ROS 2 Humble (Jammy) ====
FROM osrf/ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# ---- System deps ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-opencv python3-numpy python3-pip \
    gstreamer1.0-tools gstreamer1.0-libcamera \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    v4l-utils \
 && rm -rf /var/lib/apt/lists/*

# ---- Python deps for ROS2 image publisher ----
RUN pip3 install --no-cache-dir \
    pyyaml

# ---- App files ----
COPY camera_node.py /app/camera_node.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Defaults (override u compose env:)
ENV CAMERA_DEVICE=/dev/video0
ENV WIDTH=1280
ENV HEIGHT=720
ENV FPS=30
ENV TCP_PORT=8554
ENV CAMERA_INFO_FILE=/app/camera_info.yaml
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

ENTRYPOINT ["/entrypoint.sh"]
