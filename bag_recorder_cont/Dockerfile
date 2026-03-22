FROM ros:humble-ros-base

ENV ROS_DISTRO=humble \
    BASH_ENV=/opt/ros/humble/setup.bash

# Install ros2 bag tooling and compression plugins
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ros-humble-ros2bag \
    ros-humble-rosbag2-storage-default-plugins \
    ros-humble-rosbag2-compression-zstd \
    ros-humble-rmw-cyclonedds-cpp \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Make interactive and non-interactive bash shells immediately usable.
RUN echo 'source /opt/ros/${ROS_DISTRO}/setup.bash' >> /root/.bashrc \
    && echo 'source /opt/ros/${ROS_DISTRO}/setup.bash' >> /etc/bash.bashrc

WORKDIR /app

COPY bag_recorder.sh /app/bag_recorder.sh
RUN chmod +x /app/bag_recorder.sh

ENV TOPICS_FILE=/config/recorded_topics.yaml \
    BAG_OUTPUT_DIR=/bags \
    MAX_BAG_MB=150 \
    MAX_BAG_DURATION_S=0 \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

ENTRYPOINT ["/app/bag_recorder.sh"]
