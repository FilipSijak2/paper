import { useState, useEffect, useRef, useMemo } from 'react';
import { ConnectionParams } from '../types/connection';
import { useRos } from '../hooks/useRos';
import './MainControlView.css';
import CameraView from './CameraView';
import VisualizationPanel from './VisualizationPanel';
import StandardPadLayout from './gamepads/standard/StandardPadLayout';
import VoiceLayout from './gamepads/voice/VoiceLayout';
import GameBoyLayout from './gamepads/gameboy/GameBoyLayout';
import { DroneGamepad } from './gamepads/drone/DroneGamepad';
import { ManipulatorGamepad } from './gamepads/manipulator/ManipulatorGamepad';
import { generateUniqueId } from '../utils/helpers';
import ControlPanelTabs from './ControlPanelTabs';
import AddPanelMenu from './AddPanelMenu';
import { GamepadType } from './gamepads/GamepadInterface';
import { getGamepadLayout } from '../features/customGamepad/gamepadStorage';
import anime from 'animejs';

const IconCamera = () => (<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></svg>);
const Icon3d = () => (<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></svg>);
const IconLink = () => (<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></svg>);
const IconUnlink = () => (<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /><line x1="2" y1="2" x2="22" y2="22" /></svg>);
const IconClose = () => (<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>);

export type PanelType = GamepadType;
export interface ActivePanel { id: string; type: PanelType; name: string; layoutId?: string; }
interface MainControlViewProps { connectionParams: ConnectionParams; onDisconnect: () => void; }
type ViewMode = 'camera' | '3d';

const MainControlView = ({ connectionParams, onDisconnect }: MainControlViewProps) => {
  const [viewMode, setViewMode] = useState<ViewMode>('camera');
  const { ros, isConnected, connect, disconnect } = useRos();
  const [availableCameraTopics, setAvailableCameraTopics] = useState<string[]>([]);
  const [selectedCameraTopic, setSelectedCameraTopic] = useState<string>('');
  const initialPanelId = generateUniqueId('panel');
  const ROBOT_NAME = (import.meta.env.VITE_ROBOT_NAME as string | undefined) || 'Devastator';
  const [activePanels, setActivePanels] = useState<ActivePanel[]>([{ id: initialPanelId, type: GamepadType.Drone, name: ROBOT_NAME }]);
  const [selectedPanelId, setSelectedPanelId] = useState<string | null>(initialPanelId);
  const [isAddPanelMenuOpen, setIsAddPanelMenuOpen] = useState(false);
  const [isCustomEditorOpen, setIsCustomEditorOpen] = useState(false);
  // Remove editingLayoutId until custom editor is implemented (avoid unused warnings)
  const panelCounters = useRef<Record<PanelType, number>>({ [GamepadType.Standard]: 0, [GamepadType.Voice]: 0, [GamepadType.GameBoy]: 0, [GamepadType.Drone]: 1, [GamepadType.Manipulator]: 0, [GamepadType.Custom]: 0 });
  const [customGamepadRefreshKey, setCustomGamepadRefreshKey] = useState(0);
  const addButtonRef = useRef<HTMLButtonElement>(null);
  const viewPanelRef = useRef<HTMLDivElement>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => { if (connectionParams) connect(connectionParams); return () => disconnect(); }, [connect, disconnect, connectionParams]);
  useEffect(() => {
    if (isConnected && ros) {
      // ros.getTopics isn't typed in our minimal roslib definitions; cast to any
      (ros as any).getTopics(
        (response: { topics: string[]; types: string[] }) => {
          const imageTypes = ['sensor_msgs/Image', 'sensor_msgs/CompressedImage'];
          const potential = response.topics.filter((topic: string, index: number) =>
            imageTypes.includes(response.types[index]) ||
            topic.includes('image_raw') ||
            topic.includes('image_color') ||
            topic.includes('image_compressed')
          );
          setAvailableCameraTopics(potential);
          if (potential.length > 0 && !selectedCameraTopic) {
            const def = potential.find(t => t.includes('/image_raw')) || potential[0];
            setSelectedCameraTopic(def);
          }
        },
        (err: unknown) => {
          console.error('Failed to fetch topics', err);
          setAvailableCameraTopics([]);
          setSelectedCameraTopic('');
        }
      );
    } else {
      setAvailableCameraTopics([]);
      setSelectedCameraTopic('');
    }
  }, [isConnected, ros, selectedCameraTopic]);

  const handleViewToggle = () => {
    if (isTransitioning) return;
    setIsTransitioning(true);
    const newMode = viewMode === 'camera' ? '3d' : 'camera';
    const current = viewPanelRef.current;
    if (!current) return;
    const timeline = (anime as any).timeline({
      easing: 'easeOutQuad',
      complete: () => { setTimeout(() => setIsTransitioning(false), 200); }
    });
    const clone = current.cloneNode(true) as HTMLElement;
    clone.style.position = 'absolute';
    clone.style.top = '0';
    clone.style.left = '0';
    clone.style.width = '100%';
    clone.style.height = '100%';
    current.parentElement?.appendChild(clone);
    current.style.transform = `translateX(${newMode === '3d' ? '150%' : '-150%'})`;
    setViewMode(newMode);
    timeline.add({
      targets: [clone, current],
      translateX: (_el: HTMLElement, i: number) => i === 0 ? (newMode === '3d' ? '-150%' : '150%') : '0%',
      duration: 800,
      easing: 'easeOutQuad',
      complete: () => { clone.remove(); }
    });
  };
  const handleDisconnect = () => { disconnect(); onDisconnect(); };
  const handleSelectPanel = (id: string) => { setSelectedPanelId(id); setIsAddPanelMenuOpen(false); };
  const handleAddPanelToggle = () => setIsAddPanelMenuOpen(p => !p);
  const handleAddPanelType = (type: PanelType, layoutId?: string) => { const labels: Record<PanelType,string> = { [GamepadType.Standard]:'Pad', [GamepadType.Voice]:'Voice', [GamepadType.GameBoy]:'GameBoy', [GamepadType.Drone]:'Drone', [GamepadType.Manipulator]:'Manipulator', [GamepadType.Custom]:'Custom' }; let name: string; if (type===GamepadType.Custom && layoutId) { const item = getGamepadLayout(layoutId); name = item ? item.name : 'Custom Gamepad'; } else { panelCounters.current[type]++; name = `${labels[type]} ${panelCounters.current[type]}`; } const newPanel: ActivePanel = { id: generateUniqueId('panel'), type, name, layoutId }; setActivePanels(prev => [...prev, newPanel]); setSelectedPanelId(newPanel.id); setIsAddPanelMenuOpen(false); };
  const handleRemovePanel = (id: string) => { setActivePanels(prev => { const np = prev.filter(p => p.id !== id); if (selectedPanelId === id) setSelectedPanelId(np.length>0? np[0].id : null); return np; }); setIsAddPanelMenuOpen(false); };
  const handleCloseMenu = () => setIsAddPanelMenuOpen(false);
  const handleOpenCustomEditor = (_layoutId?: string) => { setIsCustomEditorOpen(true); setIsAddPanelMenuOpen(false); };
  // (Custom editor handlers removed until editor implementation lands to avoid unused symbol warnings)
  const handleCustomDeleted = () => setCustomGamepadRefreshKey(k=>k+1);
  const SelectedPanel = useMemo(() => {
    if (!selectedPanelId) return null;
    const panel = activePanels.find(p => p.id === selectedPanelId);
    if (!panel || !ros) return null;
    switch (panel.type) {
      case GamepadType.Standard: return <StandardPadLayout ros={ros} key={panel.id}/>;
      case GamepadType.Voice: return <VoiceLayout ros={ros} key={panel.id}/>;
      case GamepadType.GameBoy: return <GameBoyLayout ros={ros} key={panel.id}/>;
      case GamepadType.Drone: return <DroneGamepad key={panel.id}/>;
      case GamepadType.Manipulator: return <ManipulatorGamepad key={panel.id}/>;
      case GamepadType.Custom: return panel.layoutId ? <div>Custom layout {panel.layoutId}</div> : <div>Custom layout not found</div>;
      default: return <div>Unknown Panel</div>;
    }
  }, [selectedPanelId, activePanels, ros]);

  return (
    <div className="main-control-view">
      <div className="top-bar">
        <div className="view-toggle">
          <button onClick={handleViewToggle} className={viewMode==='camera' ? 'active' : ''} title="Camera View" aria-label="Camera View"><IconCamera/></button>
          <button onClick={handleViewToggle} className={viewMode==='3d' ? 'active' : ''} title="3D View" aria-label="3D View"><Icon3d/></button>
        </div>
        <div className="status-controls">
          <div className="robot-name" title={`Robot: ${ROBOT_NAME}`}>{ROBOT_NAME}</div>
            <div className={`connection-status-icon ${isConnected ? 'connected':'disconnected'}`} title={isConnected?'Connected':'Disconnected'} aria-label={isConnected?'Connected':'Disconnected'} role="status">{isConnected ? <IconLink/> : <IconUnlink/>}</div>
            <button onClick={handleDisconnect} className="disconnect-button-icon" title="Disconnect" aria-label="Disconnect"><IconClose/></button>
        </div>
      </div>
      <div className="main-content-area">
        <div className="view-panel-container">
          <div className="view-panel card" ref={viewPanelRef}>
            {viewMode==='camera' ? (
              isConnected && ros && selectedCameraTopic ? (
                <CameraView ros={ros} cameraTopic={selectedCameraTopic} availableTopics={availableCameraTopics} onTopicChange={setSelectedCameraTopic} />
              ) : (
                <div className="placeholder">{isConnected ? (availableCameraTopics.length>0 ? 'Select a camera topic':'No camera topics found') : 'Connecting to ROS...'}</div>
              )
            ) : (
              isConnected && ros ? (
                <VisualizationPanel ros={ros} isRosConnected={isConnected} ros3dViewer={{current:null}} customTFProvider={{current:null}} fixedFrame="map" onFixedFrameChange={() => {}} availableFrames={[]} displayedTfFrames={[]} onDisplayedTfFramesChange={() => {}} allTopics={[]} tfAxesScale={1} onTfAxesScaleChange={() => {}} />
              ) : (
                <div className="placeholder">Connecting to ROS...</div>
              )
            )}
          </div>
        </div>
        <div className="control-panel-container">
          <ControlPanelTabs panels={activePanels} selectedPanelId={selectedPanelId} onSelectPanel={handleSelectPanel} onAddPanelToggle={handleAddPanelToggle} onRemovePanel={handleRemovePanel} addButtonRef={addButtonRef} />
          <div className="control-panel card">{isConnected && ros ? (SelectedPanel ?? <div>Select a control panel</div>) : <div>Connecting to ROS...</div>}</div>
        </div>
      </div>
      <AddPanelMenu isOpen={isAddPanelMenuOpen} onSelectType={handleAddPanelType} onClose={handleCloseMenu} onOpenCustomEditor={handleOpenCustomEditor} addButtonRef={addButtonRef} refreshKey={customGamepadRefreshKey} onCustomGamepadDeleted={handleCustomDeleted} />
      {isCustomEditorOpen && ros && <div>Custom Gamepad Editor Placeholder</div>}
    </div>
  );
};

export default MainControlView;
