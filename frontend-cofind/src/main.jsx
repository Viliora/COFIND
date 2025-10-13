// src/main.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';
import { BrowserRouter } from 'react-router-dom'; // IMPORT INI

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {/* Menggunakan BrowserRouter untuk mengaktifkan routing */}
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);