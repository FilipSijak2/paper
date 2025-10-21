import * as React from 'react';
import { GamepadInterface } from '../GamepadInterface';

export const DroneGamepad: React.FC = () => {
  // Placeholder mapping; integrate with ROS topics later
  return (
    <div className="drone-gamepad">
      <h3>Drone Controls</h3>
      <GamepadInterface layout="drone" />
    </div>
  );
};
