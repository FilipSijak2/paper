import { useEffect, useRef, useState } from 'react';
import { Ros } from 'roslib';
import * as ROSLIB from 'roslib';
import { CustomTFProvider, TransformStore } from '../utils/tfUtils';
import * as ROS3D from '../utils/ros3d';

interface UseTfProviderProps {
  ros: Ros | null;
  isRosConnected: boolean;
  ros3dViewer: React.RefObject<ROS3D.Viewer | null>;
  fixedFrame: string;
  initialTransforms: TransformStore;
  handleTFMessage: (message: any, isStatic: boolean) => void;
}

export function useTfProvider({
  ros,
  isRosConnected,
  ros3dViewer,
  fixedFrame,
  initialTransforms,
  handleTFMessage,
}: UseTfProviderProps) {
  const customTFProvider = useRef<CustomTFProvider | null>(null);
  const tfSub = useRef<ROSLIB.Topic | null>(null);
  const tfStaticSub = useRef<ROSLIB.Topic | null>(null);
  const [isProviderReady, setIsProviderReady] = useState<boolean>(false);

  useEffect(() => {
    if (ros && isRosConnected && ros3dViewer.current) {
      if (!customTFProvider.current) {
        customTFProvider.current = new CustomTFProvider(fixedFrame, initialTransforms);
        ros3dViewer.current.fixedFrame = fixedFrame;
        setIsProviderReady(true);
      } else {
        const currentFixed = customTFProvider.current.fixedFrame;
        const normalizedNew = fixedFrame.startsWith('/') ? fixedFrame.substring(1) : fixedFrame;
        if (currentFixed !== normalizedNew) {
          if (ros3dViewer.current) ros3dViewer.current.fixedFrame = normalizedNew;
          customTFProvider.current.updateFixedFrame(normalizedNew);
          // Viewer has no public render() method; forcing a resize to trigger redraw
          if (ros3dViewer.current) {
            try {
              // Force a no-op resize using current bounding client rect of container element
              const containerEl = document.getElementById((ros3dViewer.current as any).divID || '');
              if (containerEl) {
                const rect = containerEl.getBoundingClientRect();
                const w = Math.max(1, Math.floor(rect.width));
                const h = Math.max(1, Math.floor(rect.height));
                ros3dViewer.current.resize(w, h);
              }
            } catch {}
          }
        }
        if (!isProviderReady) setIsProviderReady(true);
      }
    } else {
      if (customTFProvider.current) {
        customTFProvider.current.dispose();
        customTFProvider.current = null;
      }
      if (isProviderReady) setIsProviderReady(false);
    }
  }, [ros, isRosConnected, ros3dViewer, fixedFrame, initialTransforms, isProviderReady]);

  useEffect(() => {
    const cleanupSubscriptions = () => {
      tfSub.current?.unsubscribe(); tfSub.current = null;
      tfStaticSub.current?.unsubscribe(); tfStaticSub.current = null;
    };
    if (isProviderReady && ros && customTFProvider.current) {
      if (!tfSub.current) {
        tfSub.current = new ROSLIB.Topic({
          ros,
          name: '/tf',
          messageType: 'tf2_msgs/TFMessage',
          throttle_rate: 25,
          queue_size: 1,
          compression: 'none'
        });
        tfSub.current.subscribe((msg: any) => handleTFMessage(msg, false));
      }
      if (!tfStaticSub.current) {
        tfStaticSub.current = new ROSLIB.Topic({
          ros,
          name: '/tf_static',
          messageType: 'tf2_msgs/TFMessage',
          throttle_rate: 1000,
          queue_size: 1,
          compression: 'none'
        });
        tfStaticSub.current.subscribe((msg: any) => handleTFMessage(msg, true));
      }
    } else {
      cleanupSubscriptions();
    }
    return cleanupSubscriptions;
  }, [isProviderReady, ros, handleTFMessage]);

  const ensureProviderFunctionality = () => {
    if (!customTFProvider.current) return false;
    const required = ['lookupTransform','updateFixedFrame','subscribe','unsubscribe'];
    for (const m of required) if (typeof (customTFProvider.current as any)[m] !== 'function') return false;
    if (typeof (customTFProvider.current as any).getFixedFrame !== 'function') {
      (customTFProvider.current as any).getFixedFrame = function() { return this.fixedFrame; };
    }
    return true;
  };
  useEffect(() => { if (customTFProvider.current) ensureProviderFunctionality(); }, [isProviderReady]);
  return { customTFProvider, ensureProviderFunctionality };
}
