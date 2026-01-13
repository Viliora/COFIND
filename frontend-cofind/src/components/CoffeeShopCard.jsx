// src/components/CoffeeShopCard.jsx
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import OptimizedImage from './OptimizedImage';
import { getCoffeeShopImage } from '../utils/coffeeShopImages'; // Fallback untuk local assets
import { getValidPhotoUrl, isValidPhotoUrl } from '../utils/photoUrlHelper';
import { getReviewSummary } from '../utils/reviewSummary';
 

const CoffeeShopCard = ({ shop }) => {
    const [reviewSummary, setReviewSummary] = useState(null);
    const [isLoadingSummary, setIsLoadingSummary] = useState(false);
    const [isModalOpen] = useState(false);
    const [photoUrl, setPhotoUrl] = useState(null);
    const [useFallback, setUseFallback] = useState(false);

    // Initialize photo URL
    useEffect(() => {
      if (!shop.place_id) return;
      
      // Try Supabase URL first
      const validPhotoUrl = getValidPhotoUrl(shop.photo_url, shop.place_id);
      
      if (isValidPhotoUrl(validPhotoUrl)) {
        setPhotoUrl(validPhotoUrl);
        setUseFallback(false);
      } else {
        // Use local asset fallback immediately if Supabase URL invalid
        setPhotoUrl(getCoffeeShopImage(shop.place_id || shop.name));
        setUseFallback(true);
      }
    }, [shop.photo_url, shop.place_id, shop.name]);

    // Fetch review summary saat component mount
    useEffect(() => {
        if (shop.place_id) {
            setIsLoadingSummary(true);
            getReviewSummary(shop.place_id, shop.name)
                .then(summary => {
                    setReviewSummary(summary);
                    setIsLoadingSummary(false);
                })
                .catch(error => {
                    console.error('[CoffeeShopCard] Error loading summary:', error);
                    setIsLoadingSummary(false);
                });
        }
    }, [shop.place_id, shop.name]);

    // Handle image load error - fallback to local asset
    const handleImageError = () => {
      if (!useFallback) {
        console.log(`[CoffeeShopCard] Supabase URL failed for ${shop.name}, falling back to local asset`);
        setPhotoUrl(getCoffeeShopImage(shop.place_id || shop.name));
        setUseFallback(true);
      }
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

    // Ensure place_id exists
    if (!shop.place_id) {
      console.warn('[CoffeeShopCard] Missing place_id for shop:', shop.name);
      return null;
    }

    return (
        <div className="relative w-full">
        <Link
            to={`/shop/${shop.place_id}`}
            className="block bg-white dark:bg-gray-800 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 border border-gray-100 dark:border-gray-700 overflow-hidden group w-full"
            style={{ pointerEvents: isModalOpen ? 'none' : 'auto' }}
                onClick={(e) => {
                    // Prevent navigation if modal is open
                    if (isModalOpen) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                }}
            >
                <div className="aspect-w-16 aspect-h-9 relative overflow-hidden h-48">
                    <OptimizedImage
                        src={photoUrl}
                        alt={shop.name}
                        className="w-full h-full object-cover transform group-hover:scale-105 transition duration-300"
                        fallbackColor={getPlaceholderColor(shop.name)}
                        onError={handleImageError}
                    />
                    {shop.rating && (
                        <div className="absolute top-2 right-2 bg-white/90 backdrop-blur-sm px-2 py-1 rounded-full flex items-center shadow-lg z-10">
                            <span className="text-yellow-500 mr-1">⭐</span>
                            <span className="font-semibold">{shop.rating}</span>
                        </div>
                    )}
                </div>
            
            <div className="p-4">
                    <h2 className="text-xl font-bold text-gray-800 dark:text-gray-200 mb-2 line-clamp-2 group-hover:text-indigo-600 transition-colors">
                        {shop.name}
                    </h2>
                
                <div className="flex items-center gap-2 mb-3">
                    {statusInfo && (
                        <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${statusInfo.class}`}>
                            {statusInfo.text}
                        </span>
                    )}
                    {shop.user_ratings_total > 0 && (
                        <span className="text-sm text-gray-500">
                            ({shop.user_ratings_total} reviews)
                        </span>
                    )}
                </div>
                
                {/* Review Summary */}
                {isLoadingSummary && !reviewSummary && (
                    <div className="mb-3">
                        <div className="h-4 bg-gray-100 dark:bg-gray-700 rounded animate-pulse w-3/4"></div>
                    </div>
                )}
                {reviewSummary && (
                    <div className="mb-3 flex items-start gap-2">
                        <svg 
                            className="w-4 h-4 text-teal-500 dark:text-teal-400 mt-0.5 flex-shrink-0" 
                            fill="currentColor" 
                            viewBox="0 0 20 20"
                        >
                            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2 flex-1">
                            {reviewSummary}
                        </p>
                    </div>
                )}
                
                {shop.vicinity && (
                    <p className="text-gray-600 text-sm mb-3 line-clamp-2">
                        📍 {shop.vicinity}
                    </p>
                )}
                
                {shop.opening_hours?.open_now !== undefined && (
                    <p className={`text-sm font-medium ${shop.opening_hours.open_now ? 'text-green-600' : 'text-red-600'}`}>
                        {shop.opening_hours.open_now ? '🕒 Currently Open' : '🕒 Currently Closed'}
                    </p>
                )}
                
                <div className="mt-4 flex justify-between items-center">
                    <div className="flex flex-wrap gap-2">
                        {shop.types?.slice(0, 2).map((type, index) => (
                            <span key={index} className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded">
                                {type.replace(/_/g, ' ')}
                            </span>
                        ))}
                    </div>
                    <div className="text-indigo-500 group-hover:translate-x-1 transition-transform inline-flex items-center">
                        View Details
                        <svg className="w-4 h-4 ml-1" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                        </svg>
                    </div>
                </div>
            </div>
        </Link>
        
        {/* AI Analysis disabled */}
        </div>
    );
}

export default CoffeeShopCard;
