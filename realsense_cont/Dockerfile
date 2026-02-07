FROM ros:humble

RUN set -e; apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-realsense2-camera \
    ros-humble-realsense2-description \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Zagreb

WORKDIR /app

COPY start_realsense.sh /app/start_realsense.sh
RUN chmod +x /app/start_realsense.sh

RUN echo "export AMENT_TRACE_SETUP_FILES=\${AMENT_TRACE_SETUP_FILES:-}" >> /root/.bashrc && \
    echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "export PS1='\[\033[1;34m\]realsense_cont: \[\033[0m\]'" >> /root/.bashrc

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    RS_CAMERA_NAME=realsense \
    RS_SERIAL= \
    RS_ENABLE_DEPTH=true \
    RS_ENABLE_COLOR=true \
    RS_ENABLE_INFRA1=false \
    RS_ENABLE_INFRA2=false \
    RS_ENABLE_GYRO=true \
    RS_ENABLE_ACCEL=true \
    RS_UNITE_IMU_METHOD=linear_interpolation \
    RS_DEPTH_PROFILE=640x480x15 \
    RS_COLOR_PROFILE=640x480x15 \
    RS_ALIGN_DEPTH=true \
    RS_ENABLE_POINTCLOUD=false

CMD ["/app/start_realsense.sh"]
