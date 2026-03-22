FROM ros:jazzy-ros-base

# Install ros2 bag tooling and compression plugins
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ros-jazzy-ros2bag \
    ros-jazzy-rosbag2-storage-default-plugins \
    ros-jazzy-rosbag2-compression-zstd \
    ros-jazzy-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY bag_recorder.sh /app/bag_recorder.sh
RUN chmod +x /app/bag_recorder.sh

ENV TOPICS_FILE=/config/recorded_topics.yaml \
    BAG_OUTPUT_DIR=/bags \
    MAX_BAG_MB=150 \
    MAX_BAG_DURATION_S=0

ENTRYPOINT ["/app/bag_recorder.sh"]
