import { useEffect, useRef } from 'react';
import { Ros } from 'roslib';
import * as ROS3D from '../utils/ros3d';
import { CustomTFProvider } from '../utils/tfUtils';
import { LaserScanOptions } from '../components/visualizers/LaserScanViz';

interface UseLaserScanClientProps {
  ros: Ros | null;
  isRosConnected: boolean;
  ros3dViewer: React.RefObject<ROS3D.Viewer | null>;
  customTFProvider: React.RefObject<CustomTFProvider | null>;
  fixedFrame: string;
  selectedLaserScanTopic: string;
  material?: Partial<LaserScanOptions>;
  options?: { maxRange?: number; minRange?: number };
  clientRef: React.MutableRefObject<ROS3D.LaserScan | null>;
}

export const useLaserScanClient = ({
  ros,
  isRosConnected,
  ros3dViewer,
  customTFProvider,
  fixedFrame,
  selectedLaserScanTopic,
  material,
  options,
  clientRef,
}: UseLaserScanClientProps) => {
  const internalClientRef = useRef<ROS3D.LaserScan | null>(null);
  useEffect(() => {
    if (!ros || !isRosConnected || !ros3dViewer.current || !customTFProvider.current || !selectedLaserScanTopic) {
      if (internalClientRef.current) {
        internalClientRef.current.unsubscribe();
        internalClientRef.current = null;
        clientRef.current = null;
      }
      return;
    }
    if (internalClientRef.current && ((internalClientRef.current as any).topicName !== selectedLaserScanTopic || internalClientRef.current.fixedFrame !== fixedFrame)) {
      internalClientRef.current.unsubscribe();
      internalClientRef.current = null;
    }
    if (!internalClientRef.current) {
      internalClientRef.current = new ROS3D.LaserScan({
        ros,
        topic: selectedLaserScanTopic,
        tfClient: customTFProvider.current,
        rootObject: ros3dViewer.current.scene,
        fixedFrame,
        material: { size: material?.pointSize, color: material?.pointColor },
        maxRange: options?.maxRange,
        minRange: options?.minRange,
      });
      clientRef.current = internalClientRef.current;
    }
    return () => {
      if (internalClientRef.current) {
        internalClientRef.current.unsubscribe();
        internalClientRef.current = null;
        clientRef.current = null;
      }
    };
  }, [ros, isRosConnected, ros3dViewer, customTFProvider, fixedFrame, selectedLaserScanTopic, material, options, clientRef]);
  return { laserScanClient: internalClientRef.current };
};
