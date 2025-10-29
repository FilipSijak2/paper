# ROS 2 Humble base (Ubuntu 22.04)
FROM ros:humble

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3-pip python3-opencv python3-numpy \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav \
    ros-humble-cv-bridge \
    ros-humble-camera-info-manager \
    && rm -rf /var/lib/apt/lists/*

# App
WORKDIR /app
COPY src/ src/
COPY launch/ launch/
COPY config/ config/

# Default envs (mogu se pregaziti iz compose/.env)
ENV CAMERA_PORT=5000
ENV FRAME_ID=camera_optical_frame
ENV WIDTH=1280
ENV HEIGHT=720
ENV FPS=30
ENV CAMERA_INFO_PATH=/app/config/camera_info.yaml
ENV ROS_DOMAIN_ID=0
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV ROS_NAMESPACE=camera

# Autostart
CMD ["bash", "-lc", "source /opt/ros/humble/setup.bash && ros2 launch /app/launch/camera_launch.py"]




