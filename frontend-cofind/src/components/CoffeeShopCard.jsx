// src/components/CoffeeShopCard.jsx
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import OptimizedImage from './OptimizedImage';
import { getCoffeeShopImage } from '../utils/coffeeShopImages';

const CoffeeShopCard = ({ shop, variant = 'default' }) => {
    const [isModalOpen] = useState(false);
    const [photoUrl, setPhotoUrl] = useState(null);
    const [showRatingInfoBubble, setShowRatingInfoBubble] = useState(false);
    const isMini = variant === 'mini';

    useEffect(() => {
      if (!shop.place_id) return;
      setPhotoUrl(getCoffeeShopImage(shop.place_id || shop.name));
    }, [shop.photo_url, shop.place_id, shop.name]);

    const handleImageError = () => {
      setPhotoUrl(getCoffeeShopImage(shop.place_id || shop.name));
    };

    // Fungsi untuk mendapatkan warna placeholder berdasarkan nama shop
    const getPlaceholderColor = (shopName) => {
        const seed = shopName ? shopName.length % 10 : 0;
        const colors = [
            '#4F46E5', // indigo
            '#7C3AED', // purple
            '#EC4899', // pink
            '#F59E0B', // amber
            '#10B981', // green
            '#3B82F6', // blue
            '#8B5CF6', // violet
            '#F97316', // orange
            '#06B6D4', // cyan
            '#6366F1'  // indigo
        ];
        return colors[seed % colors.length];
    };

    const formatStatus = (status) => {
        if (!status) return null;
        const statusMap = {
            'OPERATIONAL': { text: 'Open', class: 'bg-green-100 text-green-700' },
            'CLOSED_TEMPORARILY': { text: 'Temporarily Closed', class: 'bg-yellow-100 text-yellow-700' },
            'CLOSED_PERMANENTLY': { text: 'Permanently Closed', class: 'bg-red-100 text-red-700' },
            'CLOSED': { text: 'Closed', class: 'bg-red-100 text-red-700' }
        };
        return statusMap[status] || { text: status, class: 'bg-gray-100 text-gray-700' };
    };

    const statusInfo = formatStatus(shop.business_status);

    // Rating untuk tampilan bintang (1-5), total reviews dari API (total_reviews atau user_ratings_total)
    const rating = shop.rating != null ? Number(shop.rating) : 0;
    const totalReviews = shop.total_reviews ?? shop.user_ratings_total ?? 0;

    // Komponen bintang: 5 bintang, isi berdasarkan rating (mis. 4.7 = 4 penuh + 1 sebagian)
    const renderStars = () => {
        const stars = [];
        for (let i = 1; i <= 5; i++) {
            const fill = Math.min(1, Math.max(0, rating - i + 1));
            if (fill >= 1) {
                stars.push(<span key={i} className="text-amber-400" aria-hidden>★</span>);
            } else if (fill > 0) {
                stars.push(
                    <span key={i} className="inline-block relative text-amber-400" aria-hidden>
                        <span className="text-gray-300 dark:text-gray-500">★</span>
                        <span className="absolute left-0 top-0 overflow-hidden text-amber-400" style={{ width: `${fill * 100}%` }}>★</span>
                    </span>
                );
            } else {
                stars.push(<span key={i} className="text-gray-300 dark:text-gray-500" aria-hidden>★</span>);
            }
        }
        return stars;
    };

    // Ensure place_id exists
    if (!shop.place_id) {
      console.warn('[CoffeeShopCard] Missing place_id for shop:', shop.name);
      return null;
    }

    return (
        <div className="relative w-full">
        <Link
            to={`/shop/${shop.place_id}`}
            className="block group w-full overflow-visible"
            style={{ pointerEvents: isModalOpen ? 'none' : 'auto' }}
                onClick={(e) => {
                    // Prevent navigation if modal is open
                    if (isModalOpen) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                }}
            >
            <div className={`bg-white dark:bg-gray-800 rounded-xl transition-all duration-300 border border-gray-100 dark:border-gray-700 overflow-visible ${
                isMini ? 'shadow-sm hover:shadow-md' : 'shadow-lg hover:shadow-xl'
            }`}>
                <div className={`aspect-w-16 aspect-h-9 relative overflow-hidden rounded-t-xl ${
                    isMini ? 'h-32' : 'h-48'
                }`}>
                    <OptimizedImage
                        src={photoUrl}
                        alt={shop.name}
                        className="w-full h-full object-cover object-center transform group-hover:scale-105 transition duration-300"
                        fallbackColor={getPlaceholderColor(shop.name)}
                        onError={handleImageError}
                    />
                </div>
            
            <div className={`relative ${isMini ? 'p-3' : 'p-4'}`}>
                    <h2 className={`${isMini ? 'text-base mb-1.5' : 'text-xl mb-2'} font-bold text-gray-800 dark:text-gray-200 line-clamp-2 group-hover:text-indigo-600 transition-colors`}>
                        {shop.name}
                    </h2>

                {/* Rating seperti di foto: bintang + angka + total reviews + ikon (i) */}
                <div className={`relative flex items-center gap-2 flex-wrap ${isMini ? 'mb-1.5' : 'mb-2'}`}>
                    <div className="flex items-center gap-1.5">
                        <span className={`flex leading-none ${isMini ? 'text-base' : 'text-lg'}`} aria-label={`Rating ${rating} dari 5`}>
                            {renderStars()}
                        </span>
                        {rating > 0 && (
                            <>
                                <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">{rating.toFixed(1)}</span>
                                {totalReviews > 0 && (
                                    <span className="text-sm text-gray-500 dark:text-gray-400">({totalReviews} reviews)</span>
                                )}
                                {!isMini && (
                                    <button
                                        type="button"
                                        onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            setShowRatingInfoBubble(!showRatingInfoBubble);
                                        }}
                                        className="w-5 h-5 rounded-full border border-gray-400 dark:border-gray-500 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex-shrink-0"
                                        title="Informasi rating dan ulasan"
                                        aria-label="Informasi rating dan ulasan"
                                    >
                                        <span className="text-xs font-bold leading-none">i</span>
                                    </button>
                                )}
                            </>
                        )}
                    </div>
                    {!isMini && statusInfo && (
                        <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${statusInfo.class}`}>
                            {statusInfo.text}
                        </span>
                    )}
                    {/* Bubble info: rating & reviews berdasarkan Google Maps */}
                    {!isMini && showRatingInfoBubble && (
                        <div
                            className="absolute left-0 top-full mt-1 w-64 p-3 bg-gray-100 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg z-50 text-sm text-gray-700 dark:text-gray-300"
                            role="tooltip"
                            onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                            }}
                        >
                            <p>Rating dan total ulasan berdasarkan data dari Google Maps.</p>
                            <button
                                type="button"
                                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowRatingInfoBubble(false); }}
                                className="mt-2 text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                            >
                                Tutup
                            </button>
                        </div>
                    )}
                </div>

                {!isMini && shop.opening_hours_display != null && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 flex items-center gap-1.5 line-clamp-2">
                        <span aria-hidden>🕐</span>
                        {shop.opening_hours_display || 'Jam operasional belum diisi'}
                    </p>
                )}

                {!isMini && shop.vicinity && (
                    <p className="text-gray-600 text-sm mb-3 line-clamp-2">
                        📍 {shop.vicinity}
                    </p>
                )}
                
                {!isMini && shop.opening_hours?.open_now !== undefined && (
                    <p className={`text-sm font-medium ${shop.opening_hours.open_now ? 'text-green-600' : 'text-red-600'}`}>
                        {shop.opening_hours.open_now ? '🕒 Currently Open' : '🕒 Currently Closed'}
                    </p>
                )}
                
                {!isMini && (
                <div className="mt-4 flex justify-between items-center">
                    <div className="flex items-center gap-3">
                        <div className="flex flex-wrap gap-2">
                            {shop.types?.slice(0, 2).map((type, index) => (
                                <span key={index} className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded">
                                    {type.replace(/_/g, ' ')}
                                </span>
                            ))}
                        </div>
                    </div>
                    
                    <div className="text-indigo-500 group-hover:translate-x-1 transition-transform inline-flex items-center">
                        View Details
                        <svg className="w-4 h-4 ml-1" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                        </svg>
                    </div>
                </div>
                )}
            </div>
            </div>
        </Link>
        
        </div>
    );
}

export default CoffeeShopCard;
