import { useState, useEffect, useRef } from 'react';
import { ConnectionParams } from '../types/connection';
import './EntrySection.css';
import anime from 'animejs';
import { animateLandingPage, animateAdvancedForm, animateButtonPress } from '../utils/animations';

interface EntrySectionProps { onConnect: (params: ConnectionParams) => void; }

const GearIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"></circle>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
  </svg>
);

const EntrySection = ({ onConnect }: EntrySectionProps) => {
  const [ros2Option, setRos2Option] = useState<'domain' | 'ip'>('ip');
  const [ros2Value, setRos2Value] = useState<string>('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const logoRef = useRef<HTMLDivElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const quickConnectRef = useRef<HTMLButtonElement>(null);
  const dashRef = useRef<HTMLSpanElement>(null);
  const transitionOverlayRef = useRef<HTMLDivElement>(null);
  const [themeColors, setThemeColors] = useState({ primary: '', hover: '' });
  const currentHostname = window.location.hostname;

  useEffect(() => {
    const checkTheme = () => {
      const style = getComputedStyle(document.documentElement);
      const primary = style.getPropertyValue('--primary-color').trim();
      const hover = style.getPropertyValue('--primary-hover-color').trim();
      if (primary !== themeColors.primary || hover !== themeColors.hover) {
        setThemeColors({ primary, hover });
      }
    };
    checkTheme();
    const observer = new MutationObserver(checkTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, [themeColors.primary, themeColors.hover]);

  useEffect(() => { animateLandingPage(containerRef.current, logoRef.current); }, []);
  useEffect(() => {
    animateAdvancedForm(formRef.current, showAdvanced);
    const gearIcon = document.querySelector('.advanced-toggle-content svg');
    if (gearIcon) {
      anime({ targets: gearIcon, rotate: showAdvanced ? 180 : 0, duration: 500, easing: 'easeInOutQuad' });
    }
  }, [showAdvanced]);

  useEffect(() => {
    if (!dashRef.current) return;
    // Timeline for dash animation
    const dashTimeline = anime.timeline({ loop: true, direction: 'alternate', easing: 'easeInOutSine' });
    dashTimeline
      .add({ targets: dashRef.current, rotate: [ { value: -15, duration: 400, easing: 'easeInOutBack' }, { value: 15, duration: 600, easing: 'easeInOutBack' }, { value: -8, duration: 300, easing: 'easeInOutBack' }, { value: 8, duration: 400, easing: 'easeInOutBack' }, { value: 0, duration: 500, easing: 'easeInOutBack' } ], duration: 2200 })
      .add({ targets: dashRef.current, translateY: [ { value: -4, duration: 300, easing: 'easeOutExpo' }, { value: 0, duration: 600, easing: 'easeInElastic' } ], scale: [ { value: 1.2, duration: 300, easing: 'easeOutExpo' }, { value: 1, duration: 600, easing: 'easeInElastic' } ], duration: 900, offset: '-=1000' });
    return () => { dashTimeline.pause(); };
  }, [themeColors]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const params: ConnectionParams = { ros2Option, ros2Value: ros2Option === 'domain' ? parseInt(ros2Value, 10) || 0 : ros2Value };
    const submitBtn = (e.currentTarget as HTMLFormElement).querySelector('button[type="submit"]');
    if (submitBtn) animateButtonPress(submitBtn as HTMLElement);
    onConnect(params);
  };

  const handleQuickConnect = () => {
    if (isTransitioning) return;
    setIsTransitioning(true);
    const button = quickConnectRef.current; const overlay = transitionOverlayRef.current; if (!button || !overlay) return;
    const buttonRect = button.getBoundingClientRect();
    const buttonCenterX = buttonRect.left + buttonRect.width / 2; const buttonCenterY = buttonRect.top + buttonRect.height / 2;
    button.style.opacity = '0'; button.style.pointerEvents = 'none';
    overlay.style.left = `${buttonCenterX}px`; overlay.style.top = `${buttonCenterY}px`; overlay.style.width = `${buttonRect.width}px`; overlay.style.height = `${buttonRect.height}px`; overlay.style.borderRadius = '4px'; overlay.style.display = 'block';
    const timeline = anime.timeline({ easing: 'easeInOutQuad', complete: () => { onConnect({ ros2Option: 'ip', ros2Value: currentHostname }); } });
    timeline
      .add({ targets: overlay, width: 20, height: 20, borderRadius: 50, duration: 300 })
      .add({ targets: overlay, translateY: [ { value: window.innerHeight - 10 - buttonCenterY, duration: 500, easing: 'easeInQuad' } ] })
      .add({ targets: overlay, width: '200vmax', height: '200vmax', duration: 600, easing: 'easeOutQuad' });
  };

  return (
    <div className="entry-section-container" ref={containerRef}>
      <div className="entry-section card" data-testid="entry-section">
        <div className="logo-container" ref={logoRef}>
          <h1 className="app-title"><span className="title-robo">Robo</span><span className="title-dash" ref={dashRef}>-</span><span className="title-boy">Boy</span></h1>
        </div>
        <div className="connection-options">
          <button className="quick-connect-btn" onClick={handleQuickConnect} title={`Connect to ${currentHostname}`} ref={quickConnectRef} style={{ position: 'relative', transition: 'opacity 0.1s ease' }} disabled={isTransitioning}>Quick Connect<span className="quick-connect-ip">{currentHostname}</span></button>
          <button type="button" className="advanced-toggle" onClick={() => setShowAdvanced(!showAdvanced)} title="Advanced Options" style={{ padding: '12px 16px', minWidth: '48px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}><span className="advanced-toggle-content"><GearIcon /></span></button>
          <form onSubmit={handleSubmit} ref={formRef} className={`advanced-form ${showAdvanced ? 'visible' : ''}`}>
            <div className="form-group"><label>Connection Method:</label><div className="radio-group">
              <label><input type="radio" value="domain" checked={ros2Option === 'domain'} onChange={() => setRos2Option('domain')} />Domain ID</label>
              <label><input type="radio" value="ip" checked={ros2Option === 'ip'} onChange={() => setRos2Option('ip')} />IP Address</label>
            </div></div>
            <div className="form-group"><label htmlFor="ros2Value">{ros2Option === 'domain' ? 'Domain ID:' : 'IP Address:'}</label><input type={ros2Option === 'domain' ? 'number' : 'text'} id="ros2Value" value={ros2Value} onChange={(e) => setRos2Value(e.target.value)} placeholder={ros2Option === 'domain' ? 'e.g., 0' : 'e.g., 192.168.1.100'} required /></div>
            <button type="submit" className="connect-btn">Connect</button>
          </form>
        </div>
      </div>
      <div ref={transitionOverlayRef} style={{ position: 'fixed', backgroundColor: themeColors.primary, transform: 'translate(-50%, -50%)', zIndex: 1000, display: 'none', pointerEvents: 'none' }} />
    </div>
  );
};

export default EntrySection;
