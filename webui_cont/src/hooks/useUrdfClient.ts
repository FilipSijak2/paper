import { useEffect, useRef, useState } from 'react';
import { Ros } from 'roslib';
import * as ROS3D from '../utils/ros3d';
import { CustomTFProvider } from '../utils/tfUtils';

interface UseUrdfClientProps { ros: Ros | null; isRosConnected: boolean; ros3dViewer: React.RefObject<ROS3D.Viewer | null>; tfClient: React.RefObject<CustomTFProvider | null>; robotDescriptionTopic?: string; urdfPath?: string; }
export function useUrdfClient({ ros, isRosConnected, ros3dViewer, tfClient, robotDescriptionTopic = '/robot_description', urdfPath = '/' }: UseUrdfClientProps) {
  const urdfClientRef = useRef<ROS3D.UrdfClient | null>(null);
  const [isUrdfLoaded, setIsUrdfLoaded] = useState(false);
  useEffect(() => {
    if (isRosConnected && ros && ros3dViewer.current && tfClient.current && !urdfClientRef.current) {
      const urdfClient = new ROS3D.UrdfClient({
        ros,
        tfClient: tfClient.current,
        rootObject: ros3dViewer.current.scene,
        robotDescriptionTopic,
        onComplete: () => { setIsUrdfLoaded(true); }
      } as any); // cast to any to allow custom path without strict typing
      urdfClientRef.current = urdfClient;
    } else if ((!isRosConnected || !ros3dViewer.current || !tfClient.current) && urdfClientRef.current) {
      urdfClientRef.current.dispose(); urdfClientRef.current = null; setIsUrdfLoaded(false);
    }
    return () => { if (urdfClientRef.current) { urdfClientRef.current.dispose(); urdfClientRef.current = null; setIsUrdfLoaded(false); } };
  }, [isRosConnected, ros, ros3dViewer, tfClient, robotDescriptionTopic, urdfPath]);
  return { urdfClient: urdfClientRef.current, isUrdfLoaded };
}
