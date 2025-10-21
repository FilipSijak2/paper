import type { FC, RefObject } from 'react';
import PoseStampedSettings from './PoseStampedSettings';
import { usePoseStampedClient } from '../../hooks/usePoseStampedClient';
import { Ros } from 'roslib';
import * as ROS3D from '../../utils/ros3d';

export interface PoseStampedVizOptions {
  visualizationType?: 'arrow'|'axes';
  scale?: number; arrowLength?: number; arrowWidth?: number; axesSize?: number;
  color?: string; trailEnabled?: boolean; maxTrailLength?: number;
}
export interface PoseStampedVizProps {
  ros: Ros | null;
  isRosConnected: boolean;
  ros3dViewer: RefObject<ROS3D.Viewer | null>;
  customTFProvider: RefObject<any>;
  topic: string;
  fixedFrame: string;
  options: PoseStampedVizOptions;
  onUpdateOptions: (patch: Partial<PoseStampedVizOptions>) => void;
  showSettings: boolean;
  onCloseSettings: () => void;
}

const PoseStampedViz: FC<PoseStampedVizProps> = ({
  ros,
  isRosConnected,
  ros3dViewer,
  customTFProvider,
  topic,
  fixedFrame,
  options,
  onUpdateOptions,
  showSettings,
  onCloseSettings,
}) => {
  usePoseStampedClient({
    ros,
    isRosConnected,
    ros3dViewer,
    customTFProvider,
    topic,
    fixedFrame,
    options,
  });

  const handleSettingsChange = (patch: Partial<PoseStampedVizOptions>) => {
    onUpdateOptions(patch);
  };

  return (
    <>
      {showSettings && (
        <PoseStampedSettings
          options={options}
          onChange={handleSettingsChange}
          onClose={onCloseSettings}
        />
      )}
    </>
  );
};

export default PoseStampedViz;
