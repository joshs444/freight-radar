import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
// maplibre CSS first so our own rules (.fr-globe sizing) win on equal specificity.
import 'maplibre-gl/dist/maplibre-gl.css';
import './styles.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
