import { useRef, useCallback, type FC, type RefObject } from 'react';
import { Color } from 'three';
import { usePointCloudClient } from '../../hooks/usePointCloudClient';
import { Ros } from 'roslib';
import * as ROS3D from '../../utils/ros3d';
import PointCloudSettings from './PointCloudSettings';

export interface PointCloudVizOptions {
  pointSize?: number;
  scaleX?: number; scaleY?: number; scaleZ?: number;
  originX?: number; originY?: number; originZ?: number;
  colorMode?: 'x'|'y'|'z'|'';
  minColor?: string; maxColor?: string;
  minAxisValue?: number; maxAxisValue?: number;
}

export interface PointCloudVizProps {
  ros: Ros | null;
  isRosConnected: boolean;
  ros3dViewer: RefObject<ROS3D.Viewer | null>;
  customTFProvider: RefObject<any>;
  topic: string;
  fixedFrame: string;
  options: PointCloudVizOptions;
  onUpdateOptions: (patch: Partial<PointCloudVizOptions>) => void;
  showSettings: boolean;
  onCloseSettings: () => void;
}

const PointCloudViz: FC<PointCloudVizProps> = ({
  ros,
  isRosConnected,
  ros3dViewer,
  customTFProvider,
  topic,
  fixedFrame,
  options,
  onUpdateOptions,
  showSettings,
  onCloseSettings
}) => {
  const clientRef = useRef<ROS3D.PointCloud2 | null>(null);

  const pointCloudClient = usePointCloudClient({
    ros,
    isRosConnected,
    ros3dViewer,
    customTFProvider,
    selectedPointCloudTopic: topic,
    fixedFrame,
    material: {
      size: options.pointSize,
  colorMode: options.colorMode === '' ? undefined : options.colorMode,
  minColor: options.minColor ? new Color(options.minColor) : undefined,
  maxColor: options.maxColor ? new Color(options.maxColor) : undefined,
      minAxisValue: options.minAxisValue,
      maxAxisValue: options.maxAxisValue,
    },
    options: { throttleRate: 100 },
    clientRef,
  });

  const handleSettingsChange = useCallback((patch: Partial<PointCloudVizOptions>) => {
    onUpdateOptions(patch);
    if (clientRef.current && patch.pointSize) {
      clientRef.current.updateSettings({ pointSize: patch.pointSize });
    }
    if (clientRef.current) {
      clientRef.current.updateSettings({
        scaleX: patch.scaleX,
        scaleY: patch.scaleY,
        scaleZ: patch.scaleZ,
        originX: patch.originX,
        originY: patch.originY,
        originZ: patch.originZ,
      });
    }
  }, [onUpdateOptions]);

  return (
    <>
      {showSettings && (
        <PointCloudSettings
          options={options}
          onChange={handleSettingsChange}
          onClose={onCloseSettings}
          axisRanges={(pointCloudClient as any).axisRanges}
        />
      )}
    </>
  );
};

export default PointCloudViz;
