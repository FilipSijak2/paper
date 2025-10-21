import { useRef, useCallback, type FC, type RefObject } from 'react';
import { Ros } from 'roslib';
import * as ROS3D from '../../utils/ros3d';
import { useLaserScanClient } from '../../hooks/useLaserScanClient';
import LaserScanSettings from './LaserScanSettings';

export interface LaserScanOptions {
  pointSize?: number;
  pointColor?: string;
  maxRange?: number;
  minRange?: number;
}

interface LaserScanVizProps {
  ros: Ros | null;
  isRosConnected: boolean;
  ros3dViewer: RefObject<ROS3D.Viewer | null>;
  customTFProvider: RefObject<any>;
  topic: string;
  fixedFrame: string;
  options: LaserScanOptions;
  onUpdateOptions: (patch: Partial<LaserScanOptions>) => void;
  showSettings: boolean;
  onCloseSettings: () => void;
}

const LaserScanViz: FC<LaserScanVizProps> = ({
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
  const clientRef = useRef<ROS3D.LaserScan | null>(null);

  useLaserScanClient({
    ros,
    isRosConnected,
    ros3dViewer,
    customTFProvider,
    fixedFrame,
    selectedLaserScanTopic: topic,
    material: { pointSize: options.pointSize, pointColor: options.pointColor },
    options: { maxRange: options.maxRange, minRange: options.minRange },
    clientRef,
  });

  const handleSettingsChange = useCallback((patch: Partial<LaserScanOptions>) => {
    onUpdateOptions(patch);
    if (clientRef.current) {
      clientRef.current.updateSettings({
        pointSize: patch.pointSize,
        pointColor: patch.pointColor,
        maxRange: patch.maxRange,
        minRange: patch.minRange,
      });
    }
  }, [onUpdateOptions]);

  return (
    <>
      {showSettings && (
        <LaserScanSettings
          options={options}
          onChange={handleSettingsChange}
          onClose={onCloseSettings}
        />
      )}
    </>
  );
};

export default LaserScanViz;
