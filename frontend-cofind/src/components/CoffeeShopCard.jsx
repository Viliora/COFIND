// src/components/CoffeeShopCard.jsx
import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import OptimizedImage from './OptimizedImage';
import { getCoffeeShopImage } from '../utils/coffeeShopImages';
import {
  openingHoursForTodayFromShop,
  parseJsonField,
  priceLevelLabel,
} from '../utils/googlePlacesDisplay';

/** Grid katalog di samping Latest Reviews: 3 kolom agar kartu tidak terpotong aside */
export const SHOP_CATALOG_GRID_CLASS =
  'grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-5';

/** Item carousel: 2 kartu penuh di mobile, 3 di layar lebih lebar */
export const SHOP_CAROUSEL_ITEM_CLASS =
  'relative block shrink-0 snap-start overflow-hidden w-[calc((100%-1rem)/2)] min-w-[calc((100%-1rem)/2)] sm:w-[calc((100%-2rem)/3)] sm:min-w-[calc((100%-2rem)/3)]';

const CoffeeShopCard = ({ shop, variant = 'default' }) => {
    const [isModalOpen] = useState(false);
    const isMini = variant === 'mini';
    const photoUrl = useMemo(
      () => getCoffeeShopImage(shop.place_id || shop.name),
      [shop.place_id, shop.name],
    );
    const priceLabel = priceLevelLabel(
      shop.price_level ?? parseJsonField(shop.google_places_snapshot)?.price_level,
    );
    const hoursToday = openingHoursForTodayFromShop(shop);
    const openNow = parseJsonField(shop.google_places_snapshot)?.opening_hours?.open_now;

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
        <div className="relative w-full h-full">
        <Link
            to={`/shop/${shop.place_id}`}
            className="block group w-full h-full overflow-visible"
            style={{ pointerEvents: isModalOpen ? 'none' : 'auto' }}
                onClick={(e) => {
                    // Prevent navigation if modal is open
                    if (isModalOpen) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                }}
            >
            <div className={`bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 overflow-hidden h-full flex flex-col shadow-lg hover:shadow-2xl transition duration-300 ${
                isMini ? 'min-h-[14.5rem]' : 'min-h-[21.5rem]'
            }`}>
                <div className={`aspect-w-16 aspect-h-9 relative overflow-hidden rounded-t-xl ${
                    isMini ? 'h-32' : 'h-40'
                }`}>
                    <OptimizedImage
                        src={photoUrl}
                        alt={shop.name}
                        className="w-full h-full object-cover object-center transform group-hover:scale-105 transition duration-300"
                        fallbackColor={getPlaceholderColor(shop.name)}
                    />
                </div>
            
            <div className={`relative flex-1 ${isMini ? 'p-3' : 'p-4'}`}>
                    <h2 className={`${isMini ? 'text-base mb-1.5' : 'text-lg mb-2'} font-bold text-gray-800 dark:text-gray-200 line-clamp-2 group-hover:text-indigo-600 transition-colors`}>
                        {shop.name}
                    </h2>

                {/* Rating: bintang + angka + total reviews */}
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
                            </>
                        )}
                    </div>
                </div>

                {!isMini && (hoursToday || shop.opening_hours_display != null) && (
                    <div className="text-sm text-gray-600 dark:text-gray-400 mb-2 flex items-center gap-2 flex-wrap">
                        <span className="inline-flex items-center gap-1.5 min-w-0">
                            <span aria-hidden>🕐</span>
                            <span className="truncate">
                                {hoursToday || 'Jam operasional belum diisi'}
                            </span>
                        </span>
                        {openNow !== undefined && (
                            <span
                                className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${
                                    openNow
                                        ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                                        : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                                }`}
                            >
                                {openNow ? 'Open' : 'Closed'}
                            </span>
                        )}
                    </div>
                )}

                {!isMini && shop.vicinity && (
                    <p className="text-gray-600 text-sm mb-3 line-clamp-2">
                        📍 {shop.vicinity}
                    </p>
                )}
                
                {!isMini && priceLabel && (
                    <p className="text-sm text-emerald-700 dark:text-emerald-300 mb-1">
                        💰 {priceLabel}
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
