import { useState, useEffect, ChangeEvent } from 'react';
import { GamepadInterface } from '../GamepadInterface';

interface CustomButton { id: string; label: string; action: string; }

const STORAGE_KEY = 'roboboy_custom_gamepad';

export const CustomGamepadEditor: React.FC = () => {
  const [buttons, setButtons] = useState<CustomButton[]>([]);
  const [label, setLabel] = useState('');
  const [action, setAction] = useState('');

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setButtons(JSON.parse(raw));
    } catch {}
  }, []);

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(buttons)); } catch {}
  }, [buttons]);

  const addButton = () => {
    if (!label.trim() || !action.trim()) return;
    setButtons((prev: CustomButton[]) => [...prev, { id: `${Date.now()}-${Math.random()}`, label, action }]);
    setLabel(''); setAction('');
  };

  const removeButton = (id: string) => setButtons((prev: CustomButton[]) => prev.filter((b: CustomButton) => b.id !== id));

  return (
    <div className="custom-gamepad-editor">
      <h3>Custom Gamepad Editor</h3>
      <div className="editor-form">
  <input placeholder="Label" value={label} onChange={(e: ChangeEvent<HTMLInputElement>) => setLabel(e.target.value)} />
  <input placeholder="Action" value={action} onChange={(e: ChangeEvent<HTMLInputElement>) => setAction(e.target.value)} />
        <button onClick={addButton}>Add</button>
      </div>
      <ul className="buttons-list">
  {buttons.map((b: CustomButton) => (
          <li key={b.id}>
            <span>{b.label}</span>
            <code>{b.action}</code>
            <button onClick={() => removeButton(b.id)}>x</button>
          </li>
        ))}
      </ul>
      <GamepadInterface layout="custom" customButtons={buttons} />
    </div>
  );
};
