import type { FC, RefObject } from 'react';
import { useEffect, useRef, useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { PanelType } from './MainControlView';
import './AddPanelMenu.css';
import { GamepadType } from './gamepads/GamepadInterface';
// Corrected relative path (components -> ../features)
import { loadGamepadLibrary, deleteCustomGamepad } from '../features/customGamepad/gamepadStorage';
import type { GamepadLibraryItem } from '../features/customGamepad/types';

interface AddPanelMenuProps {
  isOpen: boolean;
  onSelectType: (type: PanelType, layoutId?: string) => void;
  onClose: () => void;
  onOpenCustomEditor: (layoutId?: string) => void;
  addButtonRef: RefObject<HTMLButtonElement>;
  refreshKey?: number;
  onCustomGamepadDeleted?: () => void;
}

interface PanelInfo { type: GamepadType; label: string; }
const availablePanelTypes: PanelInfo[] = [
  { type: GamepadType.Voice, label: 'Voice Control' },
  { type: GamepadType.Drone, label: 'Drone Control' },
  { type: GamepadType.Manipulator, label: 'Manipulator Control' },
  { type: GamepadType.Custom, label: 'Custom Gamepad' },
];

let portalRoot = document.getElementById('portal-root');
if (!portalRoot) {
  portalRoot = document.createElement('div');
  portalRoot.setAttribute('id', 'portal-root');
  document.body.appendChild(portalRoot);
}

const AddPanelMenu: FC<AddPanelMenuProps> = ({
  isOpen,
  onSelectType,
  onClose,
  onOpenCustomEditor,
  addButtonRef,
  refreshKey,
  onCustomGamepadDeleted,
}: AddPanelMenuProps) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});

  useEffect(() => {
    if (isOpen && addButtonRef.current && menuRef.current) {
      const buttonRect = addButtonRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const margin = viewportWidth < 480 ? 8 : viewportWidth < 768 ? 12 : 16;
      const menuWidth = Math.min(280, viewportWidth - (2 * margin));
      const spaceBelow = viewportHeight - buttonRect.bottom - margin - 20;
      const spaceAbove = buttonRect.top - margin - 20;
      const openUpward = spaceBelow < 150 && spaceAbove > spaceBelow;
      const maxHeight = Math.min(openUpward ? spaceAbove : spaceBelow, 300);
      let left = buttonRect.right - menuWidth;
      if (left < margin) left = margin;
      if (left + menuWidth > viewportWidth - margin) left = viewportWidth - menuWidth - margin;
      const gap = 8;
      let top = openUpward ? buttonRect.top - gap : buttonRect.bottom + gap;
      if (openUpward) top = Math.max(margin, top); else top = Math.min(top, viewportHeight - maxHeight - margin);
      setMenuStyle({ position: 'fixed', top: `${top}px`, left: `${left}px`, width: `${menuWidth}px`, maxHeight: `${maxHeight}px`, transform: openUpward ? 'translateY(-100%)' : 'none', opacity: 1, zIndex: 9999, overflowY: 'auto', overflowX: 'hidden', boxSizing: 'border-box' });
    } else {
      setMenuStyle({ display: 'none', transform: 'none', opacity: 0 });
    }
  }, [isOpen, addButtonRef]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node) && addButtonRef.current && !addButtonRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen, onClose, addButtonRef]);

  const gamepadLibrary = useMemo(() => loadGamepadLibrary(), [refreshKey]);
  const customGamepads: GamepadLibraryItem[] = gamepadLibrary.filter((item: GamepadLibraryItem) => !item.isDefault);
  if (!isOpen || !portalRoot) return null;

  // (Removed unused handleMenuItemClick to satisfy linter)
  const handleCustomGamepadSelect = (layoutId: string) => onSelectType(GamepadType.Custom, layoutId);
  const handleDeleteCustomGamepad = (layoutId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    deleteCustomGamepad(layoutId);
    if (onCustomGamepadDeleted) onCustomGamepadDeleted();
  };
  const handleEditCustomGamepad = (layoutId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    onOpenCustomEditor(layoutId);
  };

  return createPortal(
    <div className="add-panel-menu" ref={menuRef} style={menuStyle}>
      <div className="add-panel-menu-content" style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden' }}>
        <div className="menu-section">
          <h4>Default Layouts</h4>
          <ul>
              {availablePanelTypes.filter(p => p.type !== GamepadType.Custom).map((panelInfo: PanelInfo) => (
              <li key={panelInfo.type}>
                <button onClick={() => onSelectType(panelInfo.type)}>{panelInfo.label}</button>
              </li>
            ))}
          </ul>
        </div>
        {customGamepads.length > 0 && (
          <div className="menu-section">
            <h4>Custom Layouts</h4>
            <ul>
              {customGamepads.map((gamepad: GamepadLibraryItem) => (
                <li key={gamepad.id} className="custom-gamepad-item">
                  <button className="custom-gamepad-button" onClick={() => handleCustomGamepadSelect(gamepad.id)}>{gamepad.name}</button>
                  <button className="edit-gamepad-button" onClick={(e) => handleEditCustomGamepad(gamepad.id, e)} title="Edit custom gamepad">✏️</button>
                  <button className="delete-gamepad-button" onClick={(e) => handleDeleteCustomGamepad(gamepad.id, e)} title="Delete custom gamepad">×</button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="menu-section">
          <button className="create-custom-button" onClick={() => onOpenCustomEditor()}><span className="icon">✏️</span> Create Custom Gamepad</button>
        </div>
      </div>
    </div>,
    portalRoot
  );
};

export default AddPanelMenu;
