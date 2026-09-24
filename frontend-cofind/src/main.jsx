// src/main.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';
import { BrowserRouter } from 'react-router-dom';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { registerServiceWorker } from './utils/sw-register';
import ErrorBoundary from './components/ErrorBoundary';

// Suppress React DevTools warning
if (import.meta.env.DEV) {
  console.info = (function(original) {
    return function(...args) {
      if (typeof args[0] === 'string' && args[0].includes('React DevTools')) {
        return; // Suppress React DevTools warning
      }
      return original.apply(console, args);
    };
  })(console.info);
}

// Register Service Worker
registerServiceWorker();

// Render App
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
        <SpeedInsights debug={false} />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
);
