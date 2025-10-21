import { useEffect, useRef } from 'react';
import * as ROS3D from '../utils/ros3d';
import * as THREE from 'three';

export function useRos3dViewer(viewerRef: React.RefObject<HTMLDivElement>, isRosConnected: boolean) {
  const ros3dViewer = useRef<ROS3D.Viewer | null>(null);
  const gridClient = useRef<ROS3D.Grid | null>(null);
  const orbitControlsRef = useRef<any | null>(null);
  const resizeObserver = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    const currentViewerRef = viewerRef.current;
    let viewerInitializedThisEffect = false;

    const cleanupViewer = () => {
      if (resizeObserver.current && currentViewerRef) {
        resizeObserver.current.unobserve(currentViewerRef);
        resizeObserver.current = null;
      }
      const disposeSceneResources = (obj: THREE.Object3D) => {
        if (!obj) return;
  (obj as any).children?.forEach((child: any) => {
          disposeSceneResources(child);
          try { obj.remove(child); } catch {}
        });
  const mesh = obj as any as THREE.Mesh;
        if (mesh.geometry) { try { mesh.geometry.dispose(); } catch {} }
        const material: any = mesh.material;
        if (material) {
          if (Array.isArray(material)) material.forEach((mat: any) => { try { if (mat.map) mat.map.dispose(); mat.dispose(); } catch {} });
          else { try { if (material.map) material.map.dispose(); material.dispose(); } catch {} }
        }
      };
      if (ros3dViewer.current) {
        try {
          ros3dViewer.current.stop();
          if (ros3dViewer.current.scene) disposeSceneResources(ros3dViewer.current.scene);
          if (ros3dViewer.current.renderer?.domElement.parentElement) {
            ros3dViewer.current.renderer.domElement.parentElement.removeChild(ros3dViewer.current.renderer.domElement);
          }
          (ros3dViewer.current.renderer as any)?.dispose?.();
        } catch {}
      }
      ros3dViewer.current = null;
      gridClient.current = null;
      orbitControlsRef.current = null;
    };

    if (currentViewerRef && isRosConnected) {
      if (!ros3dViewer.current) {
        if (!currentViewerRef.id) currentViewerRef.id = `viewer-container-${Date.now()}`;
        if (currentViewerRef.clientWidth > 0 && currentViewerRef.clientHeight > 0) {
          try {
            const viewer = new ROS3D.Viewer({
              divID: currentViewerRef.id,
              width: currentViewerRef.clientWidth,
              height: currentViewerRef.clientHeight,
              antialias: true,
              background: undefined as any,
              cameraPose: { x: 3, y: 3, z: 3 }
            });
            ros3dViewer.current = viewer;
            viewerInitializedThisEffect = true;
            const grid = new ROS3D.Grid();
            viewer.addObject(grid);
            gridClient.current = grid;
            if (ROS3D.OrbitControls) {
              orbitControlsRef.current = new ROS3D.OrbitControls({
                scene: viewer.scene,
                camera: viewer.camera,
                userZoomSpeed: 0.2,
                userPanSpeed: 0.2,
                element: currentViewerRef
              });
            }
            const observer = new ResizeObserver(entries => {
              const entry = entries[0];
              if (entry && ros3dViewer.current) {
                const { width, height } = entry.contentRect;
                if (width > 0 && height > 0) ros3dViewer.current.resize(width, height);
              }
            });
            observer.observe(currentViewerRef);
            resizeObserver.current = observer;
          } catch (error) {
            console.error('[useRos3dViewer] Init error:', error);
            cleanupViewer();
          }
        }
      }
    } else {
      cleanupViewer();
    }

    return cleanupViewer;
  }, [viewerRef, isRosConnected]);

  return { ros3dViewer };
}
