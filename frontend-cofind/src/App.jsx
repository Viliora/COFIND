// src/App.jsx
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import ShopList from './pages/ShopList';
import ShopDetail from './pages/ShopDetail';
import Favorite from './pages/Favorite';
import WantToVisit from './pages/WantToVisit';
import About from './pages/About';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import LLMAnalyzer from './components/LLMAnalyzer';

function App() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 w-full">
      {/* 1. Navbar (fixed di atas) */}
      <Navbar /> 
      
      {/* 2. Main Content (padding untuk menghindari navbar) */}
      <main className="pt-14 sm:pt-16 w-full"> 
        <Routes>
          <Route path="/" element={<ShopList />} /> 
          <Route path="/shop/:id" element={<ShopDetail />} />
          <Route path="/favorite" element={<Favorite />} />
          <Route path="/want-to-visit" element={<WantToVisit />} />
          <Route path="/about" element={<About />} />
          <Route path="/ai-analyzer" element={<LLMAnalyzer />} />
        </Routes>
      </main>
      
      {/* 3. Footer (di bawah) */}
      <Footer />
    </div>
  );
}

export default App;