// src/components/OptimizedImage.jsx
import React, { useState, useEffect, useRef } from 'react';

/**
 * OptimizedImage Component
 * Fitur:
 * - Lazy loading (hanya load saat terlihat di viewport)
 * - Progressive loading (blur placeholder -> sharp image)
 * - Error handling dengan fallback
 * - Skeleton loading state
 */
const OptimizedImage = ({ 
  src, 
  alt, 
  className = '', 
  fallbackColor = '#4F46E5',
  shopName = 'Coffee Shop'
}) => {
  const [imageState, setImageState] = useState('loading'); // loading, loaded, error
  const [imageSrc, setImageSrc] = useState(null);
  const imgRef = useRef(null);
  const observerRef = useRef(null);

  // Generate SVG placeholder
  const getPlaceholderSVG = () => {
    const svg = `
      <svg width="800" height="400" xmlns="http://www.w3.org/2000/svg">
        <rect width="800" height="400" fill="${fallbackColor}"/>
        <text x="50%" y="50%" font-family="Arial, sans-serif" font-size="48" fill="#FFFFFF" text-anchor="middle" dy=".3em">☕</text>
      </svg>
    `.trim();
    return 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)));
  };

  // Lazy loading dengan Intersection Observer
  useEffect(() => {
    if (!imgRef.current) return;

    // Jika browser tidak support IntersectionObserver, langsung load
    if (!('IntersectionObserver' in window)) {
      setImageSrc(src);
      return;
    }

    // Setup Intersection Observer
    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            // Gambar terlihat di viewport, mulai load
            setImageSrc(src);
            // Stop observing setelah mulai load
            if (observerRef.current && imgRef.current) {
              observerRef.current.unobserve(imgRef.current);
            }
          }
        });
      },
      {
        rootMargin: '50px', // Mulai load 50px sebelum masuk viewport
        threshold: 0.01
      }
    );

    if (imgRef.current) {
      observerRef.current.observe(imgRef.current);
    }

    // Cleanup
    return () => {
      if (observerRef.current && imgRef.current) {
        observerRef.current.unobserve(imgRef.current);
      }
    };
  }, [src]);

  // Handle image load success
  const handleLoad = () => {
    setImageState('loaded');
  };

  // Handle image load error
  const handleError = () => {
    setImageState('error');
    setImageSrc(getPlaceholderSVG());
  };

  return (
    <div className="relative w-full h-full overflow-hidden" ref={imgRef}>
      {/* Skeleton Loading State */}
      {imageState === 'loading' && (
        <div className="absolute inset-0 bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200 animate-pulse">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-4xl opacity-30">☕</div>
          </div>
        </div>
      )}

      {/* Actual Image */}
      {imageSrc && (
        <img
          src={imageSrc}
          alt={alt}
          className={`${className} ${
            imageState === 'loaded' ? 'opacity-100' : 'opacity-0'
          } transition-opacity duration-500 ease-in-out`}
          onLoad={handleLoad}
          onError={handleError}
          loading="lazy" // Native lazy loading sebagai fallback
          decoding="async" // Async decoding untuk performa
          fetchpriority="high" // High priority untuk hero images
          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 100vw, 1200px"
        />
      )}

      {/* Loading Spinner Overlay (opsional) */}
      {imageState === 'loading' && imageSrc && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
        </div>
      )}
    </div>
  );
};

export default OptimizedImage;

