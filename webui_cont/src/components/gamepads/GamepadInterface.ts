import * as React from 'react';
import type { Ros } from 'roslib';

/**
 * Common interface for all gamepad components
 * This ensures all gamepad types implement the same basic props
 */
export interface GamepadProps {
  ros: Ros;
  // Add other common props here if needed
}

/**
 * An enum of available gamepad types
 * Use this for type-safe references to gamepad types
 */
export enum GamepadType {
  Standard = 'standardpad',
  Voice = 'voicelayout',
  GameBoy = 'gameboy',
  Drone = 'dronepad',
  Manipulator = 'manipulatorpad',
  Custom = 'custom'
}

interface CustomButton { id: string; label: string; action: string; }

interface GamepadInterfaceProps { layout: string; customButtons?: CustomButton[]; }

// Placeholder component until full control mappings are wired
export const GamepadInterface: React.FC<GamepadInterfaceProps> = ({ layout, customButtons }: GamepadInterfaceProps) => {
  const children = (layout === 'custom' && customButtons && customButtons.length > 0)
    ? React.createElement(
        'div',
        { className: 'custom-buttons' },
  customButtons.map((btn: CustomButton) => React.createElement('button', {
          key: btn.id,
          className: 'custom-btn',
          'data-action': btn.action
        }, btn.label))
      )
    : React.createElement('p', null, `Layout: ${layout}`);
  return React.createElement('div', { className: `gamepad-interface layout-${layout}` }, children);
};
