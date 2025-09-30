FROM ros:humble

# Instaliraj ovisnosti
RUN apt-get update && apt-get install -y \
    git \
    python3-colcon-common-extensions \
    build-essential \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Postavi varijablu za CycloneDDS
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Napravi radni prostor
WORKDIR /ros2_ws
RUN mkdir src

# Kloniraj rplidar_ros s ros2 grane
RUN git clone -b ros2 https://github.com/Slamtec/rplidar_ros.git src/rplidar_ros

# Buildaj radni prostor
RUN . /opt/ros/humble/setup.sh && colcon build

# Postavi okoliš i prompt
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc && \
    echo "export PS1='\[\033[1;34m\]driver_cont: \[\033[0m\]'" >> /root/.bashrc

# Pokreni driver (ili bash ako padne)
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash && ros2 launch rplidar_ros rplidar_a1_launch.py && view_rplidar_a1_launch.py || bash"]

#test_push