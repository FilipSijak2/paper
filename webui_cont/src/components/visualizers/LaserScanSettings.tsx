import type { FC, ChangeEvent } from 'react';
import '../visualizers/TopicSettings.css';
import type { LaserScanOptions } from './LaserScanViz';

export interface LaserScanSettingsProps {
  options: LaserScanOptions;
  onChange: (patch: Partial<LaserScanOptions>) => void;
  onClose: () => void;
}

const LaserScanSettings: FC<LaserScanSettingsProps> = ({ options, onChange, onClose }) => {
  const handleNumber = (key: keyof LaserScanOptions) => (e: ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    onChange({ [key]: isNaN(value) ? undefined : value });
  };
  const handleColor = (e: ChangeEvent<HTMLInputElement>) => onChange({ pointColor: e.target.value });

  return (
    <div className="visualization-settings-popup">
      <button className="close-button" onClick={onClose}>×</button>
      <h3>LaserScan Settings</h3>
      <div className="viz-setting-group">
        <h4>Points</h4>
        <div className="viz-setting-row">
          <label htmlFor="ls-point-size">Point Size</label>
          <div className="range-input-container">
            <input id="ls-point-size" type="range" min={0.01} max={0.3} step={0.01} value={options.pointSize || 0.05} onChange={handleNumber('pointSize')} />
            <span className="range-value">{(options.pointSize || 0.05).toFixed(2)}</span>
          </div>
        </div>
        <div className="viz-setting-row">
          <label>Point Color</label>
          <input type="color" value={options.pointColor || '#ff0000'} onChange={handleColor} />
        </div>
      </div>
      <div className="viz-setting-group">
        <h4>Range Filter</h4>
        <div className="viz-inline-controls">
          <label>
            Min Range
            <input type="number" step={0.1} value={options.minRange ?? 0} onChange={handleNumber('minRange')} />
          </label>
          <label>
            Max Range
            <input type="number" step={0.1} value={options.maxRange ?? 30} onChange={handleNumber('maxRange')} />
          </label>
        </div>
      </div>
    </div>
  );
};

export default LaserScanSettings;
