import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
// maplibre CSS first so our own rules (.fr-globe sizing) win on equal specificity.
import 'maplibre-gl/dist/maplibre-gl.css';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
