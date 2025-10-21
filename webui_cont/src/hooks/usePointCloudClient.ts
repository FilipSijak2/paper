// Truncated migration: full implementation should mirror original; ensure patching logic is kept if needed.
import { useEffect, useRef } from 'react';
import { Ros } from 'roslib';
import * as ROS3D from '../utils/ros3d';
import * as THREE from 'three';
import { CustomTFProvider } from '../utils/tfUtils';

interface UsePointCloudClientProps {
  ros: Ros | null;
  isRosConnected: boolean;
  ros3dViewer: React.RefObject<ROS3D.Viewer | null>;
  customTFProvider: React.RefObject<CustomTFProvider | null>;
  selectedPointCloudTopic: string;
  fixedFrame: string;
  material?: {
    size?: number; color?: THREE.Color; colorMode?: 'x'|'y'|'z';
    minAxisValue?: number; maxAxisValue?: number; minColor?: THREE.Color; maxColor?: THREE.Color;
  };
  options?: { maxPoints?: number; throttleRate?: number };
  clientRef?: React.MutableRefObject<ROS3D.PointCloud2 | null>;
}

export function usePointCloudClient({
  ros,
  isRosConnected,
  ros3dViewer,
  customTFProvider,
  selectedPointCloudTopic,
  fixedFrame,
  material = {},
  options = {},
  clientRef
}: UsePointCloudClientProps) {
  const pointsClient = useRef<ROS3D.PointCloud2 | null>(null);
  useEffect(() => {
    if (!ros3dViewer.current || !ros || !isRosConnected || !customTFProvider.current || !selectedPointCloudTopic) {
      if (pointsClient.current) {
        try { (pointsClient.current as any).unsubscribe?.(); } catch {}
        pointsClient.current = null;
        if (clientRef) clientRef.current = null;
      }
      return;
    }
    if (pointsClient.current && (pointsClient.current as any).topic !== selectedPointCloudTopic) {
      try { (pointsClient.current as any).unsubscribe?.(); } catch {}
      pointsClient.current = null;
      if (clientRef) clientRef.current = null;
    }
    if (!pointsClient.current) {
      pointsClient.current = new ROS3D.PointCloud2({
        ros,
        topic: selectedPointCloudTopic,
        tfClient: customTFProvider.current,
        rootObject: ros3dViewer.current.scene,
        fixedFrame,
  max_pts: options.maxPoints || 100000,
        throttle_rate: options.throttleRate || 100,
        material: { size: material.size || 0.05 }
      });
      if (clientRef) clientRef.current = pointsClient.current;
    }
    return () => {
      if (pointsClient.current) {
        try { (pointsClient.current as any).unsubscribe?.(); } catch {}
        pointsClient.current = null;
        if (clientRef) clientRef.current = null;
      }
    };
  }, [ros, isRosConnected, ros3dViewer, customTFProvider, selectedPointCloudTopic, fixedFrame, material, options, clientRef]);
  return { pointsClient: pointsClient.current };
}
