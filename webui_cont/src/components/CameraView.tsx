import { useState, useEffect } from 'react';
import type { Ros } from 'roslib';
import './CameraView.css';

interface CameraViewProps {
  ros: Ros | null;
  cameraTopic: string;
  availableTopics: string[];
  onTopicChange: (newTopic: string) => void;
  streamType?: 'mjpeg' | string;
  streamWidth?: number;
  streamHeight?: number;
}

const CameraView = ({ ros, cameraTopic, availableTopics, onTopicChange, streamType='mjpeg', streamWidth, streamHeight }: CameraViewProps) => {
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ros && cameraTopic) {
      try {
        let url = `/video_stream/stream?topic=${cameraTopic}`;
        if (streamType) url += `&type=${streamType}`;
        if (streamWidth) url += `&width=${streamWidth}`;
        if (streamHeight) url += `&height=${streamHeight}`;
        setStreamUrl(url);
        setError(null);
      } catch (e) {
        setError('Failed constructing stream URL');
        setStreamUrl(null);
      }
    } else {
      setStreamUrl(null);
      setError(cameraTopic ? 'Connecting...' : 'No camera topic selected.');
    }
  }, [ros, cameraTopic, streamType, streamWidth, streamHeight]);

  return (
    <div className="camera-view">
      <div className="camera-stream-container">
  {availableTopics.length > 0 && (
          <div className="camera-topic-selector overlay">
            <select id="camera-topic-select" value={cameraTopic} onChange={(e)=> onTopicChange(e.target.value)}>
              {availableTopics.map((topic: string) => (
                <option key={topic} value={topic}>{topic}</option>
              ))}
            </select>
          </div>
        )}
        {error ? (
          <div className="error-message">{error}</div>
        ) : streamUrl ? (
          <img src={streamUrl} alt={`Stream for ${cameraTopic}`} onError={() => setError(`Failed to load stream (${streamUrl})`)} />
        ) : (
          <div className="placeholder">Waiting for stream URL...</div>
        )}
      </div>
    </div>
  );
};

export default CameraView;
