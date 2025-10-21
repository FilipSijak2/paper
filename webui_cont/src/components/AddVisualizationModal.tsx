import type { FC } from 'react';
import { useState, useMemo } from 'react';
import './AddVisualizationModal.css';

interface AddVisualizationModalProps {
  onClose: () => void;
  onAdd: (viz: { type: 'pointcloud'|'laserscan'|'posestamped'|'camerainfo'|'urdf'; topic: string; options?: any }) => void;
  allTopics: { name: string; type: string }[];
}

const SUPPORTED_TYPES: { id: 'pointcloud'|'laserscan'|'posestamped'|'camerainfo'|'urdf'; label: string; rosTypes: string[] }[] = [
  { id: 'pointcloud', label: 'PointCloud2', rosTypes: ['sensor_msgs/PointCloud2', 'sensor_msgs/msg/PointCloud2'] },
  { id: 'laserscan', label: 'LaserScan', rosTypes: ['sensor_msgs/msg/LaserScan'] },
  { id: 'posestamped', label: 'PoseStamped', rosTypes: ['geometry_msgs/PoseStamped', 'geometry_msgs/msg/PoseStamped'] },
  { id: 'camerainfo', label: 'CameraInfo', rosTypes: ['sensor_msgs/CameraInfo', 'sensor_msgs/msg/CameraInfo'] },
  { id: 'urdf', label: 'URDF Model', rosTypes: ['std_msgs/String', 'std_msgs/msg/String'] },
];

const AddVisualizationModal: FC<AddVisualizationModalProps> = ({ onClose, onAdd, allTopics }) => {
  const [selectedType, setSelectedType] = useState<'pointcloud'|'laserscan'|'posestamped'|'camerainfo'|'urdf'>('pointcloud');
  const [selectedTopic, setSelectedTopic] = useState('');
  const [manualTopic, setManualTopic] = useState('');

  const filteredTopics = useMemo(() => {
    const mapping = SUPPORTED_TYPES.find(t => t.id === selectedType);
    if (!mapping) return [];
    return allTopics.filter(t => mapping.rosTypes.includes(t.type));
  }, [selectedType, allTopics]);

  const handleAdd = () => {
    const topic = manualTopic || selectedTopic;
    if (!topic) return;
    onAdd({ type: selectedType, topic });
  };

  return (
    <div className="add-visualization-modal">
      <h3>Add Visualization</h3>
      <div className="viz-type-buttons">
        {SUPPORTED_TYPES.map(t => (
          <button
            key={t.id}
            className={selectedType === t.id ? 'active' : ''}
            onClick={() => { setSelectedType(t.id); setSelectedTopic(''); setManualTopic(''); }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="topic-select-row">
        <label>Topic (auto)</label>
        <select value={selectedTopic} onChange={(e) => setSelectedTopic(e.target.value)}>
          <option value="">Select Topic</option>
          {filteredTopics.map(t => (
            <option key={t.name} value={t.name}>{t.name}</option>
          ))}
        </select>
      </div>
      <div className="topic-select-row">
        <label>Topic (manual override)</label>
        <input type="text" placeholder="/my/topic" value={manualTopic} onChange={(e) => setManualTopic(e.target.value)} />
      </div>
      <div className="modal-actions">
        <button onClick={onClose}>Cancel</button>
        <button className="primary" disabled={!selectedTopic && !manualTopic} onClick={handleAdd}>Add</button>
      </div>
    </div>
  );
};

export default AddVisualizationModal;
