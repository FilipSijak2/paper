import { useState, useEffect, useRef, useCallback } from 'react';
import * as ROSLIB from 'roslib';
import type { Ros } from 'roslib';
import type { ConnectionParams } from '../types/connection';

interface UseRosReturn { ros: Ros | null; isConnected: boolean; connect: (params?: Partial<ConnectionParams>) => void; disconnect: () => void; }

export const useRos = (): UseRosReturn => {
  const [ros, setRos] = useState<Ros | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const rosInstanceRef = useRef<Ros | null>(null);
  const isConnectingRef = useRef<boolean>(false);

  const disconnect = useCallback(() => {
    if (rosInstanceRef.current) {
      rosInstanceRef.current.close();
      rosInstanceRef.current = null;
    }
    setIsConnected(false);
    setRos(null);
    isConnectingRef.current = false;
  }, []);

  const resolveUrl = (explicit?: string): string => {
    const envUrl = explicit || (import.meta.env.VITE_ROSBRIDGE_URL as string | undefined);
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const fallback = `${scheme}://${window.location.hostname}:9090`;
    return envUrl && envUrl.length > 0 ? envUrl : fallback;
  };

  const connect = useCallback((params?: Partial<ConnectionParams>) => {
    if (isConnectingRef.current || isConnected) return;
    if (rosInstanceRef.current) {
      rosInstanceRef.current.close();
      rosInstanceRef.current = null;
    }
    setIsConnected(false);
    setRos(null);
    isConnectingRef.current = true;

    const url = resolveUrl(params?.url);
    console.log(`[ROS CONNECT] Using URL: ${url}`);
    const newRos = new ROSLIB.Ros({ url });
    rosInstanceRef.current = newRos;

    newRos.on('connection', () => {
      if (newRos === rosInstanceRef.current) {
        setRos(newRos);
        setIsConnected(true);
        isConnectingRef.current = false;
      }
    });
    newRos.on('error', (error: Error) => {
      console.error('[ROS ERROR]', error);
      if (newRos === rosInstanceRef.current) disconnect();
    });
    newRos.on('close', () => {
      if (newRos === rosInstanceRef.current) disconnect();
    });
  }, [disconnect, isConnected]);

  useEffect(() => () => disconnect(), [disconnect]);
  return { ros, isConnected, connect, disconnect };
};
