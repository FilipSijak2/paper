import type { FC, RefObject } from 'react';
import { useUrdfClient } from '../../hooks/useUrdfClient';
import { Ros } from 'roslib';
import * as ROS3D from '../../utils/ros3d';

interface UrdfVizProps {
  ros: Ros | null;
  isRosConnected: boolean;
  ros3dViewer: RefObject<ROS3D.Viewer | null>;
  customTFProvider: RefObject<any>;
  robotDescriptionTopic?: string;
}

const UrdfViz: FC<UrdfVizProps> = ({
  ros,
  isRosConnected,
  ros3dViewer,
  customTFProvider,
  robotDescriptionTopic = '/robot_description',
}) => {
  useUrdfClient({
    ros,
    isRosConnected,
    ros3dViewer,
    tfClient: customTFProvider,
    robotDescriptionTopic,
  });
  return null;
};

export default UrdfViz;
