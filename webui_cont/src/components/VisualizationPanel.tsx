import type { FC } from 'react';
import { useState, useCallback } from 'react';
import './VisualizationPanel.css';
import { Ros } from 'roslib';
import * as ROS3D from '../utils/ros3d';
import SettingsPopup from './SettingsPopup';
import AddVisualizationModal from './AddVisualizationModal';
import PointCloudViz from './visualizers/PointCloudViz';
import LaserScanViz from './visualizers/LaserScanViz';
import PoseStampedViz from './visualizers/PoseStampedViz';
import CameraInfoViz from './visualizers/CameraInfoViz';
import UrdfViz from './visualizers/UrdfViz';

export interface VisualizationConfig {
  id: string;
  type: 'pointcloud' | 'laserscan' | 'posestamped' | 'camerainfo' | 'urdf';
  topic: string;
  options?: any;
}

interface VisualizationPanelProps {
  ros: Ros | null;
  isRosConnected: boolean;
  ros3dViewer: React.RefObject<ROS3D.Viewer | null>;
  customTFProvider: React.RefObject<any>;
  fixedFrame: string;
  onFixedFrameChange: (frame: string) => void;
  availableFrames: string[];
  displayedTfFrames: string[];
  onDisplayedTfFramesChange: (frames: string[]) => void;
  allTopics: { name: string; type: string }[];
  tfAxesScale: number;
  onTfAxesScaleChange: (scale: number) => void;
}

const VisualizationPanel: FC<VisualizationPanelProps> = ({
  ros,
  isRosConnected,
  ros3dViewer,
  customTFProvider,
  fixedFrame,
  onFixedFrameChange,
  availableFrames,
  displayedTfFrames,
  onDisplayedTfFramesChange,
  allTopics,
  tfAxesScale,
  onTfAxesScaleChange,
}) => {
  const [visualizations, setVisualizations] = useState<VisualizationConfig[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [settingsEditVizId, setSettingsEditVizId] = useState<string | null>(null);

  const handleAddVisualization = useCallback((viz: Omit<VisualizationConfig, 'id'>) => {
    setVisualizations(prev => [...prev, { ...viz, id: `${viz.type}-${Date.now()}-${Math.random().toString(36).slice(2,8)}` }]);
    setShowAddModal(false);
  }, []);

  const handleRemoveVisualization = useCallback((id: string) => {
    setVisualizations(prev => prev.filter(v => v.id !== id));
    if (settingsEditVizId === id) setSettingsEditVizId(null);
  }, [settingsEditVizId]);

  const handleUpdateVisualizationTopic = useCallback((id: string, newTopic: string) => {
    setVisualizations(prev => prev.map(v => v.id === id ? { ...v, topic: newTopic } : v));
  }, []);

  const handleEditVisualization = useCallback((id: string) => {
    setSettingsEditVizId(id);
  }, []);

  const handleUpdateOptions = useCallback((id: string, patch: any) => {
    setVisualizations(prev => prev.map(v => v.id === id ? { ...v, options: { ...(v.options||{}), ...patch } } : v));
  }, []);

  const activeVizForSettings = settingsEditVizId ? visualizations.find(v => v.id === settingsEditVizId) : null;

  return (
    <div className="visualization-panel">
      <div className="visualization-toolbar">
        <button id="viz-settings-button" className="settings-toggle-button" onClick={() => setShowSettings(s => !s)}>
          {showSettings ? 'Hide Settings' : 'Show Settings'}
        </button>
        <button className="add-visualization-button" onClick={() => setShowAddModal(true)}>Add Visualization</button>
      </div>
      <div className="viewer-container">
        <div className="viewer-canvas-wrapper" ref={ros3dViewer as any} />
        {!isRosConnected && (
          <div className="no-ros-connection-overlay">ROS Disconnected</div>
        )}
        {visualizations.map(viz => {
          const commonProps = {
            ros,
            isRosConnected,
            ros3dViewer,
            customTFProvider,
            topic: viz.topic,
            fixedFrame,
            options: viz.options || {},
            onUpdateOptions: (patch: any) => handleUpdateOptions(viz.id, patch),
            showSettings: activeVizForSettings?.id === viz.id,
            onCloseSettings: () => setSettingsEditVizId(null)
          };
          switch (viz.type) {
            case 'pointcloud':
              return <PointCloudViz key={viz.id} {...commonProps} />;
            case 'laserscan':
              return <LaserScanViz key={viz.id} {...commonProps} />;
            case 'posestamped':
              return <PoseStampedViz key={viz.id} {...commonProps} />;
            case 'camerainfo':
              return <CameraInfoViz key={viz.id} {...commonProps} />;
            case 'urdf':
              return <UrdfViz key={viz.id} {...commonProps} />;
            default:
              return null;
          }
        })}
      </div>
      {showSettings && (
        <SettingsPopup
          onClose={() => setShowSettings(false)}
          fixedFrame={fixedFrame}
          availableFrames={availableFrames}
          onFixedFrameChange={(e: React.ChangeEvent<HTMLSelectElement>) => onFixedFrameChange(e.target.value)}
          displayedTfFrames={displayedTfFrames}
          onDisplayedTfFramesChange={onDisplayedTfFramesChange}
          activeVisualizations={visualizations}
          onRemoveVisualization={handleRemoveVisualization}
          onAddVisualizationClick={() => setShowAddModal(true)}
          onEditVisualization={handleEditVisualization}
          onUpdateVisualizationTopic={handleUpdateVisualizationTopic}
          allTopics={allTopics}
          tfAxesScale={tfAxesScale}
          onTfAxesScaleChange={onTfAxesScaleChange}
        />
      )}
      {showAddModal && (
        <AddVisualizationModal
          onClose={() => setShowAddModal(false)}
          onAdd={handleAddVisualization}
          allTopics={allTopics}
        />
      )}
    </div>
  );
};

export default VisualizationPanel;
