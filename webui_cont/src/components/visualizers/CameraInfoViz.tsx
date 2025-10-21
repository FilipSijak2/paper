import type { FC, RefObject } from 'react';
import { useCameraInfoVisualizer } from '../../hooks/useCameraInfoVisualizer';
import { Ros } from 'roslib';
import * as ROS3D from '../../utils/ros3d';

interface CameraInfoVizProps {
  ros: Ros | null;
  isRosConnected: boolean;
  ros3dViewer: RefObject<ROS3D.Viewer | null>;
  customTFProvider: RefObject<any>;
  topic: string;
  lineColor?: string;
  lineScale?: number;
}

const CameraInfoViz: FC<CameraInfoVizProps> = ({
  ros,
  isRosConnected,
  ros3dViewer,
  customTFProvider,
  topic,
  lineColor = '#00ff00',
  lineScale = 1.0,
}) => {
  useCameraInfoVisualizer({
    ros,
    isRosConnected,
    ros3dViewer,
    customTFProvider,
    selectedCameraInfoTopic: topic,
    lineColor,
    lineScale,
  });
  return null;
};

export default CameraInfoViz;
