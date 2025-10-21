import { useEffect, useRef, useState } from 'react';
import { Ros } from 'roslib';
import * as ROSLIB from 'roslib';
import * as ROS3D from '../utils/ros3d';
import * as THREE from 'three';
import { CustomTFProvider } from '../utils/tfUtils';

interface UseCameraInfoVisualizerProps {
  ros: Ros | null; isRosConnected: boolean; ros3dViewer: React.RefObject<ROS3D.Viewer | null>;
  customTFProvider: React.RefObject<CustomTFProvider | null>; selectedCameraInfoTopic: string | null;
  lineColor?: THREE.Color | number | string; lineScale?: number;
}
const DEFAULT_LINE_COLOR = 0x00ff00; const DEFAULT_LINE_SCALE = 1.0;
const CAMERA_FRAME_ROTATION = new THREE.Quaternion();
export function useCameraInfoVisualizer({ ros, isRosConnected, ros3dViewer, customTFProvider, selectedCameraInfoTopic, lineColor = DEFAULT_LINE_COLOR, lineScale = DEFAULT_LINE_SCALE }: UseCameraInfoVisualizerProps) {
  const cameraInfoSub = useRef<ROSLIB.Topic | null>(null);
  const frustumLinesRef = useRef<THREE.LineSegments | null>(null);
  const frustumContainerRef = useRef<THREE.Group | null>(null);
  const [lastCameraInfo, setLastCameraInfo] = useState<any>(null);
  const [cameraFrameId, setCameraFrameId] = useState<string | null>(null);
  const animationFrameId = useRef<number | null>(null);
  useEffect(() => {
    const viewer = ros3dViewer.current;
    if (isRosConnected && viewer && selectedCameraInfoTopic) {
      if (!frustumContainerRef.current) {
  frustumContainerRef.current = new THREE.Group(); (frustumContainerRef.current as any).visible = false; viewer.scene.add(frustumContainerRef.current);
        if (!frustumLinesRef.current) {
          const vertices = new Float32Array(15);
          const initialGeometry = new THREE.BufferGeometry();
          initialGeometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
          (initialGeometry as any).setIndex?.([]);
          const material = new THREE.LineBasicMaterial({ color: lineColor as any });
          frustumLinesRef.current = new THREE.LineSegments(initialGeometry, material as any) as any;
          (frustumLinesRef.current as any).visible = false; (frustumContainerRef.current as any).add(frustumLinesRef.current as any);
        }
      } else if (frustumLinesRef.current && (frustumLinesRef.current.material as any).color && (frustumLinesRef.current.material as any).color.getHex?.() !== new THREE.Color(lineColor as any).getHex()) {
        (frustumLinesRef.current.material as any).color.set(lineColor as any);
      }
    } else if (frustumContainerRef.current) {
      ros3dViewer.current?.scene.remove(frustumContainerRef.current);
      frustumLinesRef.current?.geometry?.dispose(); (frustumLinesRef.current?.material as THREE.Material)?.dispose(); frustumContainerRef.current = null; frustumLinesRef.current = null;
    }
    return () => {
      if (frustumContainerRef.current && viewer) {
        try {
          viewer.scene.remove(frustumContainerRef.current);
          frustumLinesRef.current?.geometry?.dispose(); (frustumLinesRef.current?.material as THREE.Material)?.dispose();
        } catch {}
        frustumContainerRef.current = null; frustumLinesRef.current = null;
      }
    };
  }, [isRosConnected, selectedCameraInfoTopic, ros3dViewer, lineColor]);
  useEffect(() => {
    const cleanupSubscription = () => { if (cameraInfoSub.current) { cameraInfoSub.current.unsubscribe(); cameraInfoSub.current = null; setLastCameraInfo(null); } };
    if (ros && isRosConnected && selectedCameraInfoTopic) {
      cleanupSubscription(); const sub = new ROSLIB.Topic({ ros, name: selectedCameraInfoTopic, messageType: 'sensor_msgs/msg/CameraInfo', throttle_rate: 200 });
      sub.subscribe((message: any) => { setLastCameraInfo(message); const frame = message.header?.frame_id; if (frame) { const cleanedFrame = frame.startsWith('/') ? frame.substring(1) : frame; setCameraFrameId((prev: string | null) => prev !== cleanedFrame ? cleanedFrame : prev); } else { setCameraFrameId(null); } }); cameraInfoSub.current = sub;
    } else { cleanupSubscription(); setCameraFrameId(null); setLastCameraInfo(null); }
    return cleanupSubscription;
  }, [ros, isRosConnected, selectedCameraInfoTopic]);
  useEffect(() => {
  const lines = frustumLinesRef.current as any; if (!lines || !lines.geometry) return; if (!lastCameraInfo) { lines.visible = false; return; }
    const K = lastCameraInfo.k; const width = lastCameraInfo.width; const height = lastCameraInfo.height;
    if (!K || K.length < 6 || !width || !height) { lines.visible = false; return; }
    const fx = K[0]; const fy = K[4]; const cx = K[2]; const cy = K[5]; const Z = lineScale;
    const points = [[0,0,0],[((0-cx)*Z)/fx,((0-cy)*Z)/fy,Z],[((width-cx)*Z)/fx,((0-cy)*Z)/fy,Z],[((width-cx)*Z)/fx,((height-cy)*Z)/fy,Z],[((0-cx)*Z)/fx,((height-cy)*Z)/fy,Z]];
    const indices = [0,1,0,2,0,3,0,4,1,2,2,3,3,4,4,1];
  const positionAttribute = lines.geometry.getAttribute('position') as any; if (!positionAttribute) return; const positionArray = positionAttribute.array as Float32Array;
    for (let i=0;i<points.length;i++){ const base=i*3; positionArray[base]=points[i][0]; positionArray[base+1]=points[i][1]; positionArray[base+2]=points[i][2]; }
  positionAttribute.needsUpdate = true; const indexAttribute = lines.geometry.getIndex(); if (!indexAttribute || (indexAttribute as any).array.length !== indices.length) (lines.geometry as any).setIndex?.(indices); lines.visible = true;
  }, [lastCameraInfo, lineScale]);
  useEffect(() => {
    const updatePose = () => {
  const viewer = ros3dViewer.current; const provider = customTFProvider.current; const container = frustumContainerRef.current as any;
  if (!isRosConnected || !viewer || !provider || !container || !cameraFrameId) { if (container) container.visible = false; animationFrameId.current = requestAnimationFrame(updatePose); return; }
      const fixedFrame = viewer.fixedFrame || 'odom';
      try {
        const transform = provider.lookupTransform(fixedFrame, cameraFrameId);
        if (transform && transform.translation && transform.rotation) {
          container.position.set(transform.translation.x, transform.translation.y, transform.translation.z);
          const tfQuaternion = new THREE.Quaternion(transform.rotation.x, transform.rotation.y, transform.rotation.z, transform.rotation.w);
          container.quaternion.copy(tfQuaternion); if (CAMERA_FRAME_ROTATION) container.quaternion.multiply(CAMERA_FRAME_ROTATION); container.visible = true;
  } else { container.visible = false; }
  } catch { container.visible = false; }
      animationFrameId.current = requestAnimationFrame(updatePose);
    };
    if (isRosConnected && frustumContainerRef.current) animationFrameId.current = requestAnimationFrame(updatePose);
    return () => { if (animationFrameId.current) { cancelAnimationFrame(animationFrameId.current); animationFrameId.current = null; } if (frustumContainerRef.current) frustumContainerRef.current.visible = false; };
  }, [isRosConnected, ros3dViewer, customTFProvider, cameraFrameId]);
  return { lastCameraInfo, cameraFrameId };
}
