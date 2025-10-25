FROM ros:humble

# Install v4l2 camera driver and RMW implementation
RUN apt-get update && apt-get install -y \
    ros-humble-v4l2-camera \
    ros-humble-image-tools \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Set default RMW
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Default command to run the camera node
CMD ["ros2", "run", "v4l2_camera", "v4l2_camera_node", "--ros-args", "-p", "camera_info_url:=file:///camera_info.yaml"]
