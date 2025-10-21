import type { FC, ChangeEvent } from 'react';
import '../visualizers/TopicSettings.css';
import './PointCloudSettings.css';
// Removed unused THREE shim import

export interface PointCloudSettingsValues {
  pointSize?: number;
  scaleX?: number; scaleY?: number; scaleZ?: number;
  originX?: number; originY?: number; originZ?: number;
  colorMode?: 'x'|'y'|'z'|'';
  minColor?: string; maxColor?: string;
  minAxisValue?: number; maxAxisValue?: number;
}
export interface PointCloudSettingsProps {
  options: PointCloudSettingsValues;
  onChange: (patch: Partial<PointCloudSettingsValues>) => void;
  onClose: () => void;
  axisRanges?: { x: {min:number,max:number}; y:{min:number,max:number}; z:{min:number,max:number} };
}

const PointCloudSettings: FC<PointCloudSettingsProps> = ({ options, onChange, onClose, axisRanges }) => {
  const handleNumber = (key: keyof PointCloudSettingsValues) => (e: ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    onChange({ [key]: isNaN(value) ? undefined : value });
  };

  const handleColor = (key: keyof PointCloudSettingsValues) => (e: ChangeEvent<HTMLInputElement>) => {
    onChange({ [key]: e.target.value });
  };

  const handleAxisMode = (mode: ''|'x'|'y'|'z') => {
    onChange({ colorMode: mode });
  };

  const currentAxisRange = options.colorMode && axisRanges ? axisRanges[options.colorMode as 'x'|'y'|'z'] : undefined;

  return (
    <div className="visualization-settings-popup">
      <button className="close-button" onClick={onClose}>×</button>
      <h3>PointCloud Settings</h3>
      <div className="viz-setting-group">
        <h4>Geometry</h4>
        <div className="viz-setting-row">
          <label htmlFor="pc-point-size">Point Size</label>
          <div className="range-input-container">
            <input id="pc-point-size" type="range" min={0.01} max={0.4} step={0.01} value={options.pointSize || 0.05} onChange={handleNumber('pointSize')} />
            <span className="range-value">{(options.pointSize || 0.05).toFixed(2)}</span>
          </div>
        </div>
        <div className="viz-inline-controls">
          <label>
            Scale X
            <input type="number" step={0.1} value={options.scaleX ?? 1} onChange={handleNumber('scaleX')} />
          </label>
          <label>
            Scale Y
            <input type="number" step={0.1} value={options.scaleY ?? 1} onChange={handleNumber('scaleY')} />
          </label>
          <label>
            Scale Z
            <input type="number" step={0.1} value={options.scaleZ ?? 1} onChange={handleNumber('scaleZ')} />
          </label>
        </div>
        <div className="viz-inline-controls">
          <label>
            Origin X
            <input type="number" step={0.1} value={options.originX ?? 0} onChange={handleNumber('originX')} />
          </label>
          <label>
            Origin Y
            <input type="number" step={0.1} value={options.originY ?? 0} onChange={handleNumber('originY')} />
          </label>
          <label>
            Origin Z
            <input type="number" step={0.1} value={options.originZ ?? 0} onChange={handleNumber('originZ')} />
          </label>
        </div>
      </div>
      <div className="viz-setting-group">
        <h4>Color Mode</h4>
        <div className="axis-mode-select">
          {(['x','y','z'] as const).map(axis => (
            <button key={axis} className={options.colorMode === axis ? 'active' : ''} onClick={() => handleAxisMode(axis)}>
              Axis {axis.toUpperCase()}
            </button>
          ))}
          <button className={!options.colorMode ? 'active' : ''} onClick={() => handleAxisMode('')}>
            Flat
          </button>
        </div>
        {options.colorMode && (
          <>
            <div className="pointcloud-color-row">
              <div className="color-block">
                <label>Min Color</label>
                <input type="color" value={options.minColor || '#0000ff'} onChange={handleColor('minColor')} />
              </div>
              <div className="color-block">
                <label>Max Color</label>
                <input type="color" value={options.maxColor || '#ff0000'} onChange={handleColor('maxColor')} />
              </div>
            </div>
            <div className="viz-inline-controls">
              <label>
                Min Axis
                <input type="number" step={0.1} value={options.minAxisValue ?? (currentAxisRange?.min ?? -10)} onChange={handleNumber('minAxisValue')} />
              </label>
              <label>
                Max Axis
                <input type="number" step={0.1} value={options.maxAxisValue ?? (currentAxisRange?.max ?? 10)} onChange={handleNumber('maxAxisValue')} />
              </label>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default PointCloudSettings;
