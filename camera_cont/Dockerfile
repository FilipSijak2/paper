FROM ros:humble

# Install v4l2 camera driver + dependencies
RUN apt-get update && apt-get install -y \
    ros-humble-v4l2-camera \
    ros-humble-image-transport \
    ros-humble-camera-info-manager \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Set CycloneDDS (compatible with rest of stack)
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Default launch of camera node
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && ros2 run v4l2_camera v4l2_camera_node --ros-args -p video_device:=/dev/video0 -p image_width:=1280 -p image_height:=720 -p framerate:=30 -p camera_info_url:=file:///camera_info.yaml"]
