// src/App.jsx
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import ShopList from './pages/ShopList';
import ShopDetail from './pages/ShopDetail';
import Navbar from './components/Navbar'; // IMPORT BARU
import Footer from './components/Footer'; // IMPORT BARU

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      
      {/* 1. Navbar (fixed di atas) */}
      <Navbar /> 
      
      {/* 2. Main Content (padding untuk menghindari navbar) */}
      <main className="pt-20"> 
        <Routes>
          <Route path="/" element={<ShopList />} /> 
          <Route path="/shop/:id" element={<ShopDetail />} />
        </Routes>
      </main>
      
      {/* 3. Footer (di bawah) */}
      <Footer />
    </div>
  );
}

export default App;