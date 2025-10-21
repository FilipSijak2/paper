import React, { RefObject } from 'react';
import './ControlPanelTabs.css';

export interface ActivePanel { id: string; name: string; }

interface ControlPanelTabsProps {
  panels: ActivePanel[];
  selectedPanelId: string | null;
  onSelectPanel: (id: string) => void;
  onAddPanelToggle: () => void;
  onRemovePanel: (id: string) => void;
  addButtonRef: RefObject<HTMLButtonElement>;
}

const ControlPanelTabs: React.FC<ControlPanelTabsProps> = ({ panels, selectedPanelId, onSelectPanel, onAddPanelToggle, onRemovePanel, addButtonRef }) => {
  const handleRemoveClick = (e: React.MouseEvent<HTMLButtonElement>, id: string) => {
    e.stopPropagation();
    onRemovePanel(id);
  };
  return (
    <div className="control-panel-tabs-container">
      <div className="control-panel-tabs">
        {panels.map(panel => (
          <div
            key={panel.id}
            role="tab"
            tabIndex={panel.id === selectedPanelId ? 0 : -1}
            onClick={() => onSelectPanel(panel.id)}
            className={`tab-button ${panel.id === selectedPanelId ? 'active' : ''}`}
            title={panel.name}
            aria-selected={panel.id === selectedPanelId}
          >
            <span className="tab-name">{panel.name}</span>
            {panels.length > 1 && (
              <button
                onClick={(e) => handleRemoveClick(e, panel.id)}
                className="tab-remove-button"
                aria-label={`Remove ${panel.name}`}
                title="Remove Panel"
              >
                ✕
              </button>
            )}
          </div>
        ))}
        <button ref={addButtonRef} className="tab-add-button" onClick={onAddPanelToggle} aria-label="Add Panel" title="Add Panel">＋</button>
      </div>
    </div>
  );
};

export default ControlPanelTabs;
