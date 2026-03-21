FROM ros:humble-ros-base

# Install required packages
RUN apt-get update && apt-get install -y \
    python3-opencv \
    python3-pip \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    ros-humble-rmw-cyclonedds-cpp \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    ros-humble-rqt-image-view \
    gstreamer1.0-libav \
    ros-humble-cv-bridge \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir numpy

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV ROS_DOMAIN_ID=0

SHELL ["/bin/bash", "-c"]
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc

WORKDIR /app
COPY camera_node.py /app/camera_node.py

CMD ["python3", "/app/camera_node.py"]





