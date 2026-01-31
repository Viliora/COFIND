// src/components/CoffeeShopCard.jsx
import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import OptimizedImage from './OptimizedImage';
import { getCoffeeShopImage } from '../utils/coffeeShopImages';
import { getReviewSummary } from '../utils/reviewSummary';
import { useAuth } from '../context/authContext';
import { authService } from '../services/authService';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

const CoffeeShopCard = ({ shop }) => {
    const { isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const [reviewSummary, setReviewSummary] = useState(null);
    const [isLoadingSummary, setIsLoadingSummary] = useState(false);
    const [isModalOpen] = useState(false);
    const [photoUrl, setPhotoUrl] = useState(null);
    const [aiSummary, setAiSummary] = useState(null);
    const [isLoadingAI, setIsLoadingAI] = useState(false);
    const [showAiBubble, setShowAiBubble] = useState(false);
    const [showInfoBubble, setShowInfoBubble] = useState(false);
    const [showLoginPrompt, setShowLoginPrompt] = useState(false);

    // Initialize photo URL
    useEffect(() => {
      if (!shop.place_id) return;

      // Local-only image
      setPhotoUrl(getCoffeeShopImage(shop.place_id || shop.name));
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
      setPhotoUrl(getCoffeeShopImage(shop.place_id || shop.name));
    };

    // Function to fetch AI summary (hanya untuk user yang sudah login)
    const handleAISummarize = async (e) => {
        e.preventDefault();
        e.stopPropagation();

        if (!isAuthenticated) {
            setShowLoginPrompt(true);
            return;
        }
        
        if (aiSummary) {
            setShowAiBubble(!showAiBubble);
            return;
        }
        
        setIsLoadingAI(true);
        try {
            const token = authService.getToken();
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(`${API_BASE}/api/coffeeshops/${shop.place_id}/summarize`, {
                method: 'POST',
                headers
            });
            
            const data = await response.json();
            
            if (response.status === 401 || data.require_login) {
                setShowLoginPrompt(true);
                return;
            }
            if (data.status === 'success') {
                setAiSummary(data.summary);
                setShowAiBubble(true);
            } else {
                setAiSummary(data.message || 'AI tidak tersedia saat ini');
                setShowAiBubble(true);
            }
        } catch (error) {
            console.error('[AI Summarize] Error:', error);
            setAiSummary('Gagal memuat ringkasan AI');
            setShowAiBubble(true);
        } finally {
            setIsLoadingAI(false);
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
                        className="w-full h-full object-cover object-center transform group-hover:scale-105 transition duration-300"
                        fallbackColor={getPlaceholderColor(shop.name)}
                        onError={handleImageError}
                    />
                </div>
            
            <div className="p-4">
                    <h2 className="text-xl font-bold text-gray-800 dark:text-gray-200 mb-2 line-clamp-2 group-hover:text-indigo-600 transition-colors">
                        {shop.name}
                    </h2>

                {/* Rating seperti di foto: bintang + angka + total reviews + ikon (i) */}
                <div className="relative flex items-center gap-2 mb-2 flex-wrap">
                    <div className="flex items-center gap-1.5">
                        <span className="flex text-lg leading-none" aria-label={`Rating ${rating} dari 5`}>
                            {renderStars()}
                        </span>
                        {rating > 0 && (
                            <>
                                <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">{rating.toFixed(1)}</span>
                                {totalReviews > 0 && (
                                    <span className="text-sm text-gray-500 dark:text-gray-400">({totalReviews} reviews)</span>
                                )}
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        setShowInfoBubble(!showInfoBubble);
                                    }}
                                    className="w-5 h-5 rounded-full border border-gray-400 dark:border-gray-500 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex-shrink-0"
                                    title="Informasi rating dan ulasan"
                                    aria-label="Informasi rating dan ulasan"
                                >
                                    <span className="text-xs font-bold leading-none">i</span>
                                </button>
                            </>
                        )}
                    </div>
                    {statusInfo && (
                        <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${statusInfo.class}`}>
                            {statusInfo.text}
                        </span>
                    )}
                    {/* Bubble info: rating & reviews berdasarkan Google Maps */}
                    {showInfoBubble && (
                        <div
                            className="absolute left-0 top-full mt-1 w-64 p-3 bg-gray-100 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg z-50 text-sm text-gray-700 dark:text-gray-300"
                            role="tooltip"
                        >
                            <p>Rating dan total ulasan berdasarkan data dari Google Maps.</p>
                            <button
                                type="button"
                                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowInfoBubble(false); }}
                                className="mt-2 text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                            >
                                Tutup
                            </button>
                        </div>
                    )}
                </div>

                {/* Jam Operasional - di bawah nama, di atas button AI summary */}
                {shop.opening_hours_display != null && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 flex items-center gap-1.5 line-clamp-2">
                        <span aria-hidden>🕐</span>
                        {shop.opening_hours_display || 'Jam operasional belum diisi'}
                    </p>
                )}
                
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
                    <div className="flex items-center gap-3">
                        {/* AI Summarize Button - No Background */}
                        <div className="relative">
                            <button
                                onClick={handleAISummarize}
                                className="hover:scale-110 transition-transform duration-200"
                                title="AI Summary"
                                disabled={isLoadingAI}
                            >
                                {isLoadingAI ? (
                                    <div className="w-7 h-7 flex items-center justify-center">
                                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-600"></div>
                                    </div>
                                ) : (
                                    <img 
                                        src="https://img.icons8.com/3d-fluency/94/bard.png" 
                                        alt="AI Summary" 
                                        className="w-7 h-7"
                                    />
                                )}
                            </button>
                            
                            {/* AI Summary Bubble - format seperti gambar: tulisan biru, hanya isi analisis (tanpa nama) */}
                            {showAiBubble && aiSummary && (
                                <div className="absolute bottom-10 left-0 w-64 bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-900/90 dark:to-blue-900/90 backdrop-blur-sm p-3 rounded-2xl shadow-2xl border-2 border-purple-200 dark:border-purple-700 z-50 animate-fade-in">
                                    <button
                                        onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            setShowAiBubble(false);
                                        }}
                                        className="absolute -top-2 -right-2 bg-white dark:bg-gray-800 rounded-full p-1 shadow-lg hover:bg-red-50 transition-colors"
                                    >
                                        <svg className="w-4 h-4 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                    <div className="flex items-start gap-2">
                                        <img 
                                            src="https://img.icons8.com/3d-fluency/94/bard.png" 
                                            alt="AI" 
                                            className="w-6 h-6 flex-shrink-0"
                                        />
                                        <p className="text-sm text-blue-600 dark:text-blue-400 leading-relaxed font-medium">
                                            ✨ {aiSummary}
                                        </p>
                                    </div>
                                </div>
                            )}
                            {/* Popup: saran login untuk AI Summary */}
                            {showLoginPrompt && (
                                <>
                                    <div
                                        className="fixed inset-0 bg-black/40 z-[100]"
                                        aria-hidden="true"
                                        onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            setShowLoginPrompt(false);
                                        }}
                                    />
                                    <div
                                        className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(90vw,320px)] bg-white dark:bg-gray-800 border-2 border-amber-200 dark:border-amber-700 rounded-2xl shadow-2xl p-4 z-[101] animate-fade-in"
                                        role="dialog"
                                        aria-labelledby="login-prompt-title"
                                        aria-describedby="login-prompt-desc"
                                    >
                                        <p id="login-prompt-title" className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1">
                                            Fitur AI Summary
                                        </p>
                                        <p id="login-prompt-desc" className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                                            Silakan login terlebih dahulu untuk menggunakan fitur AI Summary.
                                        </p>
                                        <div className="flex gap-2">
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    setShowLoginPrompt(false);
                                                    navigate('/login');
                                                }}
                                                className="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
                                            >
                                                Login
                                            </button>
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    setShowLoginPrompt(false);
                                                }}
                                                className="px-3 py-2 text-sm font-medium rounded-lg bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
                                            >
                                                Tutup
                                            </button>
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>
                        
                        {/* Types Tags */}
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
            </div>
        </Link>
        
        {/* AI Analysis disabled */}
        </div>
    );
}

export default CoffeeShopCard;
