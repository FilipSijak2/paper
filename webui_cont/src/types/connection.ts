// Unified connection parameters used across EntrySection, MainControlView and useRos hook.
// ros2Option/ros2Value are used for UI level selection; url allows direct override.
export interface ConnectionParams {
  ros2Option: 'domain' | 'ip';
  ros2Value: string | number;
  /** Optional explicit websocket URL (ws://host:port). If provided it overrides other resolution logic */
  url?: string;
}
