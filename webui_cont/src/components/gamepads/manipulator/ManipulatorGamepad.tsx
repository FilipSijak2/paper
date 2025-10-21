import type { FC } from 'react';
import { GamepadInterface } from '../GamepadInterface';

// Simple stateless manipulator gamepad placeholder; no props yet.
export const ManipulatorGamepad: FC = () => (
  <div className="manipulator-gamepad">
    <h3>Manipulator Controls</h3>
    <GamepadInterface layout="manipulator" />
  </div>
);
