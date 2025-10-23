FROM ros:humble-ros-base
RUN apt-get update && apt-get install -y \
    ros-humble-rpicam-ros \
    ros-humble-image-transport-plugins \
    && rm -rf /var/lib/apt/lists/*
# Add video group just in case we later drop root (kept root for simplicity now)
RUN groupadd -f video && usermod -aG video root
WORKDIR /app
COPY camera_launch.py /app/camera_launch.py

# Default launch; can override params at runtime via:
#   docker run ... camera_cont ros2 launch /app/camera_launch.py width:=1920 height:=1080 fps:=15
ENTRYPOINT ["ros2", "launch", "/app/camera_launch.py"]