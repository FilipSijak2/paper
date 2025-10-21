import type { FC, ChangeEvent } from 'react';
import '../visualizers/TopicSettings.css';
import './PoseStampedSettings.css';

export interface PoseStampedSettingsValues {
  visualizationType?: 'arrow' | 'axes';
  scale?: number;
  arrowLength?: number;
  arrowWidth?: number;
  axesSize?: number;
  color?: string;
  trailEnabled?: boolean;
  maxTrailLength?: number;
}
export interface PoseStampedSettingsProps {
  options: PoseStampedSettingsValues;
  onChange: (patch: Partial<PoseStampedSettingsValues>) => void;
  onClose: () => void;
}

const PoseStampedSettings: FC<PoseStampedSettingsProps> = ({ options, onChange, onClose }) => {
  const handleNumber = (key: keyof PoseStampedSettingsValues) => (e: ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    onChange({ [key]: isNaN(value) ? undefined : value });
  };
  const handleColor = (e: ChangeEvent<HTMLInputElement>) => onChange({ color: e.target.value });
  const handleTypeChange = (e: ChangeEvent<HTMLSelectElement>) => onChange({ visualizationType: e.target.value as 'arrow'|'axes' });
  const handleCheckbox = (key: keyof PoseStampedSettingsValues) => (e: ChangeEvent<HTMLInputElement>) => onChange({ [key]: e.target.checked });

  return (
    <div className="visualization-settings-popup">
      <button className="close-button" onClick={onClose}>×</button>
      <h3>PoseStamped Settings</h3>
      <div className="viz-setting-group">
        <h4>Visualization</h4>
        <div className="viz-setting-row">
          <label>Type</label>
          <select value={options.visualizationType || 'arrow'} onChange={handleTypeChange}>
            <option value="arrow">Arrow</option>
            <option value="axes">Axes</option>
          </select>
        </div>
        <div className="pose-settings-inline">
          <div className="number-input-group">
            <label>Scale</label>
            <input type="number" step={0.1} value={options.scale ?? 1} onChange={handleNumber('scale')} />
          </div>
          <div className="number-input-group">
            <label>Arrow Length</label>
            <input type="number" step={0.1} value={options.arrowLength ?? 1} onChange={handleNumber('arrowLength')} />
          </div>
          <div className="number-input-group">
            <label>Arrow Width</label>
            <input type="number" step={0.05} value={options.arrowWidth ?? 0.1} onChange={handleNumber('arrowWidth')} />
          </div>
          <div className="number-input-group">
            <label>Axes Size</label>
            <input type="number" step={0.1} value={options.axesSize ?? 0.5} onChange={handleNumber('axesSize')} />
          </div>
        </div>
        <div className="viz-setting-row">
          <label>Color</label>
          <input type="color" value={options.color || '#00ff00'} onChange={handleColor} />
        </div>
        <div className="trail-toggle-row">
          <label>
            <input type="checkbox" checked={options.trailEnabled === true} onChange={handleCheckbox('trailEnabled')} /> Enable Trail
          </label>
          {options.trailEnabled === true && (
            <label style={{marginLeft:'auto'}}>
              Max Points
              <input style={{marginLeft:4}} type="number" min={5} max={500} step={5} value={options.maxTrailLength ?? 50} onChange={handleNumber('maxTrailLength')} />
            </label>
          )}
        </div>
      </div>
    </div>
  );
};

export default PoseStampedSettings;
