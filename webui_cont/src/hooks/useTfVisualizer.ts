import { useEffect, useRef } from 'react';
import * as ROS3D from '../utils/ros3d';
import { Group, Vector3, Quaternion } from 'three';
import { CustomTFProvider } from '../utils/tfUtils';

interface UseTfVisualizerProps {
  isRosConnected: boolean;
  ros3dViewer: React.RefObject<ROS3D.Viewer | null>;
  customTFProvider: React.RefObject<CustomTFProvider | null>;
  displayedTfFrames: string[];
  axesScale?: number;
}

type TfAxesMap = Map<string, { group: Group; axes: ROS3D.Axes }>;
const DEFAULT_AXES_SCALE = 0.5;

export function useTfVisualizer({
  isRosConnected,
  ros3dViewer,
  customTFProvider,
  displayedTfFrames,
  axesScale = DEFAULT_AXES_SCALE,
}: UseTfVisualizerProps) {
  const tfAxesContainerRef = useRef<Group | null>(null);
  const tfAxesMapRef = useRef<TfAxesMap>(new Map());
  const animationFrameId = useRef<number | null>(null);

  useEffect(() => {
    const viewer = ros3dViewer.current;
    if (isRosConnected && viewer) {
      if (!tfAxesContainerRef.current) {
  tfAxesContainerRef.current = new Group();
        viewer.scene.add(tfAxesContainerRef.current);
      }
    } else if (tfAxesContainerRef.current) {
      viewer?.scene.remove(tfAxesContainerRef.current);
      tfAxesContainerRef.current = null;
    }
  }, [isRosConnected, ros3dViewer]);

  useEffect(() => {
    const container = tfAxesContainerRef.current;
    const currentMap = tfAxesMapRef.current;
    if (!container) return;
    const framesToAdd = new Set(displayedTfFrames);
    const framesToRemove: string[] = [];
    currentMap.forEach((_, frameName) => {
      if (framesToAdd.has(frameName)) framesToAdd.delete(frameName); else framesToRemove.push(frameName);
    });
    framesToRemove.forEach(frameName => {
      const entry = currentMap.get(frameName);
      if (entry) {
        container.remove(entry.group);
        if (entry.axes.lineSegments) {
          entry.axes.lineSegments.geometry?.dispose();
          const material: any = entry.axes.lineSegments.material;
          if (Array.isArray(material)) material.forEach((m: any) => m.dispose()); else material?.dispose();
        }
        currentMap.delete(frameName);
      }
    });
    framesToAdd.forEach(frameName => {
  const group = new Group();
      const axes = new ROS3D.Axes({ lineSize: axesScale });
      group.add(axes);
      container.add(group);
      currentMap.set(frameName, { group, axes });
    });
    return () => {
      const mapToClear = tfAxesMapRef.current;
      const containerAtCleanup = tfAxesContainerRef.current;
      mapToClear.forEach(entry => {
        containerAtCleanup?.remove(entry.group);
        if (entry.axes.lineSegments) {
          entry.axes.lineSegments.geometry?.dispose();
          const material: any = entry.axes.lineSegments.material;
          if (Array.isArray(material)) material.forEach((m: any) => m.dispose()); else material?.dispose();
        }
      });
      mapToClear.clear();
    };
  }, [displayedTfFrames, axesScale]);

  useEffect(() => {
    const VISUALIZATION_REFRESH_RATE_MS = 33;
    let lastUpdateTime = 0;
  const newPos = new Vector3();
  const newQuat = new Quaternion();
    const updateAxesPoses = (timestamp: number) => {
      const viewer = ros3dViewer.current;
      const provider = customTFProvider.current;
      const container = tfAxesContainerRef.current;
      const currentMap = tfAxesMapRef.current;
      if (!isRosConnected || !viewer || !provider || !container || currentMap.size === 0) {
        animationFrameId.current = requestAnimationFrame(updateAxesPoses); return;
      }
      if (timestamp - lastUpdateTime < VISUALIZATION_REFRESH_RATE_MS) {
        animationFrameId.current = requestAnimationFrame(updateAxesPoses); return;
      }
      lastUpdateTime = timestamp;
      const fixedFrame = viewer.fixedFrame || 'odom';
  // Thresholds removed (no longer used after simplification)
    currentMap.forEach((entry, frameName) => {
        const transform = provider.lookupTransform(fixedFrame, frameName);
        if (transform && transform.translation && transform.rotation) {
          newPos.set(transform.translation.x, transform.translation.y, transform.translation.z);
          newQuat.set(transform.rotation.x, transform.rotation.y, transform.rotation.z, transform.rotation.w);
          entry.group.position.copy(newPos);
          entry.group.quaternion.copy(newQuat);
          entry.group.visible = true;
        } else if (entry.group.visible) {
          entry.group.visible = false;
        }
      });
      animationFrameId.current = requestAnimationFrame(updateAxesPoses);
    };
    if (isRosConnected && tfAxesContainerRef.current) {
      animationFrameId.current = requestAnimationFrame(updateAxesPoses);
    }
    return () => { if (animationFrameId.current) cancelAnimationFrame(animationFrameId.current); };
  }, [isRosConnected, ros3dViewer, customTFProvider]);
}
