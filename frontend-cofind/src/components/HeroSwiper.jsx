// HeroSwiper - Auto-playing carousel untuk menampilkan foto coffee shops
import React, { useEffect, useState } from 'react';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Autoplay, Pagination, Navigation, EffectFade } from 'swiper/modules';
import { Link } from 'react-router-dom';

// Import Swiper styles
import 'swiper/css';
import 'swiper/css/pagination';
import 'swiper/css/navigation';
import 'swiper/css/effect-fade';

import OptimizedImage from './OptimizedImage';
import { getAllCoffeeShopImages } from '../utils/coffeeShopImages';

const HeroSwiper = ({ coffeeShops }) => {
  const [featuredShops, setFeaturedShops] = useState([]);

  useEffect(() => {
    if (coffeeShops && coffeeShops.length > 0) {
      // Ambil coffee shops dengan rating tinggi dan assign foto dari asset
      const shopsWithPhotos = coffeeShops
        .filter(shop => shop.rating >= 4.0)
        .sort((a, b) => {
          // Sort by rating dan user_ratings_total
          const scoreA = (a.rating || 0) * 0.6 + ((a.user_ratings_total || 0) / 1000) * 0.4;
          const scoreB = (b.rating || 0) * 0.6 + ((b.user_ratings_total || 0) / 1000) * 0.4;
          return scoreB - scoreA;
        })
        .slice(0, 20) // Ambil maksimal 20 coffee shop terbaik (sesuai jumlah asset foto)
        .map((shop, index) => ({
          ...shop,
          photos: [getAllCoffeeShopImages()[index % getAllCoffeeShopImages().length]] // Assign foto dari asset secara berurutan
        }));

      setFeaturedShops(shopsWithPhotos);

      // Preload hero images untuk kualitas HD
      shopsWithPhotos.forEach((shop) => {
        if (shop.photos && shop.photos[0]) {
          const link = document.createElement('link');
          link.rel = 'preload';
          link.as = 'image';
          link.href = shop.photos[0];
          link.fetchPriority = 'high';
          document.head.appendChild(link);
        }
      });
    }
  }, [coffeeShops]);

  if (featuredShops.length === 0) {
    return null; // Jangan tampilkan jika tidak ada data
  }

  return (
    <div className="hero-swiper-container mb-6 sm:mb-8">
      <Swiper
        modules={[Autoplay, Pagination, Navigation, EffectFade]}
        spaceBetween={0}
        slidesPerView={1}
        effect="fade"
        fadeEffect={{ crossFade: true }}
        autoplay={{
          delay: 4000,
          disableOnInteraction: false,
          pauseOnMouseEnter: true,
        }}
        pagination={{
          clickable: true,
          dynamicBullets: true,
        }}
        navigation={true}
        loop={true}
        speed={800}
        className="hero-swiper"
      >
        {featuredShops.map((shop) => (
          <SwiperSlide key={shop.place_id}>
            <Link to={`/shop/${shop.place_id}`} className="block relative group">
              <div className="relative w-full h-[300px] sm:h-[400px] md:h-[500px] lg:h-[600px] overflow-hidden">
                {/* Image */}
                <OptimizedImage
                  src={shop.photos[0]}
                  alt={shop.name}
                  className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                  fallbackColor={(() => {
                    const seed = (shop.name || 'Coffee Shop').length % 10;
                    const colors = ['#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981', '#3B82F6', '#8B5CF6', '#F97316', '#06B6D4', '#6366F1'];
                    return colors[seed % colors.length];
                  })()}
                  shopName={shop.name}
                  isHero={true}
                />

                {/* Gradient Overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent"></div>

                {/* Content Overlay */}
                <div className="absolute bottom-0 left-0 right-0 p-6 sm:p-8 md:p-12 text-white">
                  <div className="max-w-4xl">
                    {/* Badge */}
                    <div className="flex items-center gap-3 mb-4">
                      <span className="inline-flex items-center px-3 py-1 bg-white/20 backdrop-blur-sm rounded-full text-sm font-semibold">
                        {shop.rating} ★
                      </span>
                      {shop.user_ratings_total > 0 && (
                        <span className="inline-flex items-center px-3 py-1 bg-white/20 backdrop-blur-sm rounded-full text-sm">
                          {shop.user_ratings_total} reviews
                        </span>
                      )}
                    </div>

                    {/* Title */}
                    <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold mb-3 sm:mb-4 drop-shadow-lg">
                      {shop.name}
                    </h2>

                    {/* Address */}
                    {shop.address && (
                      <p className="text-sm sm:text-base md:text-lg text-white/90 mb-4 flex items-start gap-2 max-w-2xl">
                        <svg className="w-5 h-5 sm:w-6 sm:h-6 flex-shrink-0 mt-0.5" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                          <path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                          <path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        </svg>
                        <span className="line-clamp-2">{shop.address}</span>
                      </p>
                    )}

                    {/* CTA Button */}
                    <button className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-300 group-hover:scale-105">
                      <span>Lihat Detail</span>
                      <svg className="w-5 h-5 transition-transform group-hover:translate-x-1" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" stroke="currentColor" viewBox="0 0 24 24">
                        <path d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Hover Overlay */}
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300"></div>
              </div>
            </Link>
          </SwiperSlide>
        ))}
      </Swiper>

      {/* Custom Styles */}
      <style jsx>{`
        .hero-swiper {
          width: 100%;
        }

        /* Optimasi gambar HD untuk hero swiper - mencegah blur */
        :global(.hero-swiper img) {
          image-rendering: auto;
          -webkit-image-rendering: -webkit-optimize-contrast;
          image-rendering: -webkit-optimize-contrast;
          backface-visibility: hidden;
          -webkit-backface-visibility: hidden;
          transform: translateZ(0);
          -webkit-transform: translateZ(0);
          -ms-transform: translateZ(0);
          will-change: transform;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }

        /* Mencegah blur saat scale/hover - gunakan GPU acceleration */
        :global(.hero-swiper .group:hover img) {
          image-rendering: auto;
          -webkit-image-rendering: -webkit-optimize-contrast;
          transform: translateZ(0) scale(1.05);
          -webkit-transform: translateZ(0) scale(1.05);
        }

        /* Custom Navigation Buttons */
        :global(.hero-swiper .swiper-button-next),
        :global(.hero-swiper .swiper-button-prev) {
          color: white;
          background: rgba(0, 0, 0, 0.5);
          backdrop-filter: blur(10px);
          width: 50px;
          height: 50px;
          border-radius: 50%;
          transition: all 0.3s;
        }

        :global(.hero-swiper .swiper-button-next:hover),
        :global(.hero-swiper .swiper-button-prev:hover) {
          background: rgba(0, 0, 0, 0.7);
          transform: scale(1.1);
        }

        :global(.hero-swiper .swiper-button-next::after),
        :global(.hero-swiper .swiper-button-prev::after) {
          font-size: 20px;
          font-weight: bold;
        }

        /* Custom Pagination */
        :global(.hero-swiper .swiper-pagination) {
          bottom: 20px;
        }

        :global(.hero-swiper .swiper-pagination-bullet) {
          width: 12px;
          height: 12px;
          background: white;
          opacity: 0.5;
          transition: all 0.3s;
        }

        :global(.hero-swiper .swiper-pagination-bullet-active) {
          opacity: 1;
          background: #4F46E5;
          width: 32px;
          border-radius: 6px;
        }

        /* Responsive adjustments */
        @media (max-width: 640px) {
          :global(.hero-swiper .swiper-button-next),
          :global(.hero-swiper .swiper-button-prev) {
            width: 40px;
            height: 40px;
          }

          :global(.hero-swiper .swiper-button-next::after),
          :global(.hero-swiper .swiper-button-prev::after) {
            font-size: 16px;
          }
        }

        /* Hide navigation on very small screens */
        @media (max-width: 480px) {
          :global(.hero-swiper .swiper-button-next),
          :global(.hero-swiper .swiper-button-prev) {
            display: none;
          }
        }
      `}</style>
    </div>
  );
};

export default HeroSwiper;

