// Migrated SettingsPopup from original project (trimmed styling dependencies)
import type { FC, ChangeEvent } from 'react';
import './VisualizationPanel.css';
import { VisualizationConfig } from './VisualizationPanel';

interface TopicInfo { name: string; type: string; }

interface SettingsPopupProps {
  onClose: () => void;
  fixedFrame: string;
  availableFrames: string[];
  onFixedFrameChange: (event: React.ChangeEvent<HTMLSelectElement>) => void;
  displayedTfFrames: string[];
  onDisplayedTfFramesChange: (frames: string[]) => void;
  activeVisualizations: VisualizationConfig[];
  onRemoveVisualization: (id: string) => void;
  onAddVisualizationClick: () => void;
  onEditVisualization?: (id: string) => void;
  onUpdateVisualizationTopic?: (id: string, newTopic: string) => void;
  allTopics: TopicInfo[];
  tfAxesScale: number;
  onTfAxesScaleChange: (newScale: number) => void;
}

const SettingsPopup: FC<SettingsPopupProps> = ({
  onClose,
  fixedFrame,
  availableFrames,
  onFixedFrameChange,
  displayedTfFrames,
  onDisplayedTfFramesChange,
  activeVisualizations,
  onRemoveVisualization,
  onAddVisualizationClick,
  onEditVisualization,
  onUpdateVisualizationTopic,
  allTopics,
  tfAxesScale,
  onTfAxesScaleChange
}) => {
  const handleTfCheckboxChange = (event: ChangeEvent<HTMLInputElement>) => {
    const frameName = event.target.value;
    const isChecked = event.target.checked;
    let newSelectedFrames: string[];
    if (isChecked) {
      newSelectedFrames = displayedTfFrames.includes(frameName) ? displayedTfFrames : [...displayedTfFrames, frameName];
    } else {
  newSelectedFrames = displayedTfFrames.filter((f: string) => f !== frameName);
    }
    onDisplayedTfFramesChange(newSelectedFrames);
  };

  const getTopicsForType = (vizType: string): TopicInfo[] => {
    const mapping: Record<string, string[]> = {
      pointcloud: ['sensor_msgs/PointCloud2','sensor_msgs/msg/PointCloud2'],
      laserscan: ['sensor_msgs/msg/LaserScan'],
      posestamped: ['geometry_msgs/PoseStamped','geometry_msgs/msg/PoseStamped'],
      camerainfo: ['sensor_msgs/CameraInfo','sensor_msgs/msg/CameraInfo'],
      urdf: ['std_msgs/String','std_msgs/msg/String']
    };
    const list = mapping[vizType] || [];
    return allTopics.filter(t => list.includes(t.type));
  };

  return (
    <div className="settings-popup">
      <div className="settings-popup-header">
        <h3>Settings</h3>
        <button onClick={onClose} className="icon-button" aria-label="Close settings">×</button>
      </div>
      <div className="popup-control-item">
        <label htmlFor="fixed-frame-select">Fixed Frame:</label>
        <select id="fixed-frame-select" value={fixedFrame} onChange={onFixedFrameChange} disabled={availableFrames.length===0}>
          {availableFrames.length === 0 ? (
            <option value="" disabled>No frames</option>
          ) : availableFrames.map(f => <option key={f} value={f}>{f}</option>)}
        </select>
      </div>
      <div className="popup-control-item">
        <label htmlFor="tf-axes-scale">TF Axes Size:</label>
        <div className="range-input-container">
          <input id="tf-axes-scale" type="range" min={0.1} max={2.0} step={0.1} value={tfAxesScale} onChange={(e)=>onTfAxesScaleChange(parseFloat(e.target.value))} />
          <span className="range-value">{tfAxesScale.toFixed(1)}</span>
        </div>
      </div>
      <div className="popup-control-item">
        <label>Displayed TF Frames:</label>
        <ul className="tf-checkbox-list">
          {availableFrames.map(frame => (
            <li key={frame}>
              <label>
                <input type="checkbox" value={frame} checked={displayedTfFrames.includes(frame)} onChange={handleTfCheckboxChange} /> {frame}
              </label>
            </li>
          ))}
        </ul>
      </div>
      <div className="section-header-with-action">
        <h4 style={{margin:0}}>Active Visualizations</h4>
        <button className="icon-button" onClick={onAddVisualizationClick} aria-label="Add Visualization">+</button>
      </div>
      <div className="active-visualizations-list">
        {activeVisualizations.length === 0 ? (
          <p className="no-visualizations-message">None</p>
        ) : (
          <ul>
            {activeVisualizations.map(viz => (
              <li key={viz.id} className="visualization-item">
                <span className="viz-type">{viz.type}</span>
                <div className="topic-dropdown-container">
                  <select value={viz.topic} onChange={(e)=> onUpdateVisualizationTopic && onUpdateVisualizationTopic(viz.id, e.target.value)} className="topic-dropdown">
                    {!getTopicsForType(viz.type).some(t => t.name === viz.topic) && (
                      <option key={viz.topic} value={viz.topic}>{viz.topic} (current)</option>
                    )}
                    {getTopicsForType(viz.type).map(t => (
                      <option key={t.name} value={t.name}>{t.name}</option>
                    ))}
                  </select>
                </div>
                {(viz.type === 'pointcloud' || viz.type === 'laserscan' || viz.type === 'posestamped') && onEditVisualization && (
                  <button className="viz-settings-button" onClick={()=> onEditVisualization(viz.id)}>⚙</button>
                )}
                <button className="remove-viz-button" onClick={()=> onRemoveVisualization(viz.id)}>✕</button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default SettingsPopup;
