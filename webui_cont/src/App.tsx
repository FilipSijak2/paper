import { useState } from 'react';
import './App.css';
import EntrySection from './components/EntrySection';
import MainControlView from './components/MainControlView';
import { ConnectionParams } from './types/connection';

function App() {
  const [connectionParams, setConnectionParams] = useState<ConnectionParams | null>(null);

  const handleConnect = (params: ConnectionParams) => {
    setConnectionParams(params);
    console.log('Connecting with:', params);
  };

  const handleDisconnect = () => {
    setConnectionParams(null);
    console.log('Disconnected');
  };

  return (
    <div className="App">
      <main>
        {!connectionParams ? (
          <EntrySection onConnect={handleConnect} />
        ) : (
          <MainControlView
            connectionParams={connectionParams}
            onDisconnect={handleDisconnect}
          />
        )}
      </main>
    </div>
  );
}

export default App;
