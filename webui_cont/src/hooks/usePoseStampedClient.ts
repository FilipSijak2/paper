import { useEffect, useRef, useCallback } from 'react';
import { Ros } from 'roslib';
import * as ROSLIB from 'roslib';
import * as ROS3D from '../utils/ros3d';
import * as THREE from 'three';
import { CustomTFProvider } from '../utils/tfUtils';

export interface PoseStampedOptions {
  visualizationType?: 'arrow' | 'axes';
  scale?: number; color?: string | THREE.Color; arrowLength?: number; arrowWidth?: number; axesSize?: number;
  showTrail?: boolean; maxTrailLength?: number; scaleEnabled?: boolean; colorEnabled?: boolean;
  arrowDimensionsEnabled?: boolean; trailEnabled?: boolean;
}
interface UsePoseStampedClientProps {
  ros: Ros | null; isRosConnected: boolean; ros3dViewer: React.RefObject<ROS3D.Viewer | null>;
  customTFProvider: React.RefObject<CustomTFProvider | null>; topic: string; fixedFrame: string; options?: PoseStampedOptions;
}
export function usePoseStampedClient({ ros, isRosConnected, ros3dViewer, customTFProvider, topic, fixedFrame, options = {} }: UsePoseStampedClientProps) {
  const topicClientRef = useRef<ROSLIB.Topic | null>(null);
  const visualizationGroupRef = useRef<THREE.Group | null>(null);
  const trailPointsRef = useRef<THREE.Vector3[]>([]);
  const trailLineRef = useRef<THREE.Line | null>(null);
  const visualizationType = options.visualizationType || 'arrow';
  const scale = options.scaleEnabled === false ? 1.0 : (options.scale || 1.0);
  const color = options.colorEnabled === false ? '#00ff00' : (options.color || '#00ff00');
  const arrowLength = options.arrowDimensionsEnabled === false ? 1.0 : (options.arrowLength || 1.0);
  const arrowWidth = options.arrowDimensionsEnabled === false ? 0.1 : (options.arrowWidth || 0.1);
  const axesSize = options.arrowDimensionsEnabled === false ? 0.5 : (options.axesSize || 0.5);
  const showTrail = options.trailEnabled === true && options.showTrail !== false;
  const maxTrailLength = options.trailEnabled === true ? (options.maxTrailLength || 50) : 50;
  const createArrow = useCallback((length: number, width: number, c: string) => {
    const group = new THREE.Group();
    const mat = new THREE.MeshLambertMaterial({ color: c });
    const shaftGeometry = new THREE.CylinderGeometry(width*0.3, width*0.3, length*0.8, 8) as unknown as THREE.BufferGeometry;
    const shaft = new THREE.Mesh(shaftGeometry, mat); shaft.rotation.z = -Math.PI/2; shaft.position.set(length*0.4,0,0); group.add(shaft);
    const headGeometry = new THREE.ConeGeometry(width, length*0.2, 8) as unknown as THREE.BufferGeometry;
    const head = new THREE.Mesh(headGeometry, mat); head.rotation.z = -Math.PI/2; head.position.set(length*0.9,0,0); group.add(head);
    return group;
  }, []);
  const createAxes = useCallback((size: number) => new ROS3D.Axes({ lineSize: size }), []);
  const updateTrail = useCallback((position: THREE.Vector3) => {
    if (!showTrail || !ros3dViewer.current) return;
    trailPointsRef.current.push(position.clone());
    if (trailPointsRef.current.length > maxTrailLength) trailPointsRef.current.shift();
    if (trailLineRef.current && visualizationGroupRef.current) {
      visualizationGroupRef.current.remove(trailLineRef.current);
      trailLineRef.current.geometry.dispose(); (trailLineRef.current.material as any).dispose?.();
    }
    if (trailPointsRef.current.length > 1) {
      const geometry = new THREE.BufferGeometry().setFromPoints(trailPointsRef.current);
      const material = new THREE.LineBasicMaterial({ color: typeof color === 'string' ? color : '#00ff00', opacity:0.6, transparent:true });
      trailLineRef.current = new THREE.Line(geometry, material);
      visualizationGroupRef.current?.add(trailLineRef.current);
    }
  }, [showTrail, maxTrailLength, color, ros3dViewer]);
  const handlePoseStampedMessage = useCallback((message: any) => {
    if (!ros3dViewer.current || !customTFProvider.current || !visualizationGroupRef.current) return;
    try {
      const { pose } = message; const { position, orientation } = pose;
  const positionVec = new THREE.Vector3(position.x, position.y, position.z);
  const quaternion = new THREE.Quaternion(orientation.x, orientation.y, orientation.z, orientation.w);
    visualizationGroupRef.current.clear?.();
      const visualization = visualizationType === 'arrow' ? createArrow(arrowLength*scale, arrowWidth*scale, typeof color === 'string' ? color : '#00ff00') : createAxes(axesSize*scale);
    visualization.position.copy(positionVec);
    visualization.quaternion.copy(quaternion);
      visualizationGroupRef.current.add(visualization);
      if (showTrail) updateTrail(positionVec);
    } catch (error) { console.error('[PoseStamped] Error processing message:', error); }
  }, [visualizationType, scale, color, arrowLength, arrowWidth, axesSize, showTrail, createArrow, createAxes, updateTrail, ros3dViewer, customTFProvider]);
  useEffect(() => {
    if (!isRosConnected || !ros || !ros3dViewer.current || !topic) return;
  if (!visualizationGroupRef.current) { visualizationGroupRef.current = new THREE.Group(); ros3dViewer.current.scene.add(visualizationGroupRef.current); }
    const topicClient = new ROSLIB.Topic({ ros, name: topic, messageType: 'geometry_msgs/msg/PoseStamped' });
    topicClient.subscribe(handlePoseStampedMessage); topicClientRef.current = topicClient;
    return () => {
      topicClientRef.current?.unsubscribe(); topicClientRef.current = null;
      if (visualizationGroupRef.current && ros3dViewer.current) {
  ros3dViewer.current.scene.remove(visualizationGroupRef.current); visualizationGroupRef.current.clear?.(); visualizationGroupRef.current = null;
      }
  if (trailLineRef.current) { trailLineRef.current.geometry.dispose(); (trailLineRef.current.material as any).dispose?.(); trailLineRef.current = null; }
      trailPointsRef.current = [];
    };
  }, [isRosConnected, ros, ros3dViewer, topic, fixedFrame, handlePoseStampedMessage]);
  useEffect(() => {
  if (visualizationGroupRef.current) {
  visualizationGroupRef.current.clear?.(); trailPointsRef.current = [];
      if (trailLineRef.current) { trailLineRef.current.geometry.dispose(); (trailLineRef.current.material as any).dispose?.(); trailLineRef.current = null; }
    }
  }, [visualizationType, scale, color, arrowLength, arrowWidth, axesSize, showTrail, maxTrailLength]);
  return { isSubscribed: !!topicClientRef.current, visualizationGroup: visualizationGroupRef.current };
}
