FROM ros:humble

# Install v4l2 camera driver and dependencies
RUN apt-get update && apt-get install -y \
    ros-humble-v4l2-camera \
    ros-humble-image-tools \
    && rm -rf /var/lib/apt/lists/*

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Set the entrypoint to run the camera node
CMD ["ros2", "run", "v4l2_camera", "v4l2_camera_node", "--ros-args", "-p", "camera_info_url:=file:///camera_info.yaml"]
