// src/components/CoffeeShopCard.jsx
import React from 'react';

const CoffeeShopCard = ({ shop }) => {
    const defaultImage = 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=80';

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
    
    // Mengambil foto dari shop.photos dan jika tidak ada, menggunakan gambar default
    const photoUrl = shop.photos && shop.photos.length > 0 
        ? shop.photos[0] 
        : defaultImage;

    return (
        <div className="bg-white rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 border border-gray-100 overflow-hidden group">
            <div className="aspect-w-16 aspect-h-9 relative overflow-hidden">
                <img 
                    src={photoUrl}
                    alt={shop.name}
                    className="w-full h-48 object-cover transform group-hover:scale-105 transition duration-300"
                    onError={(e) => {
                        e.target.onerror = null;
                        e.target.src = defaultImage;  // Jika gambar gagal dimuat, tampilkan gambar default
                    }}
                />
                {shop.rating && (
                    <div className="absolute top-2 right-2 bg-white/90 backdrop-blur-sm px-2 py-1 rounded-full flex items-center shadow-lg">
                        <span className="text-yellow-500 mr-1">⭐</span>
                        <span className="font-semibold">{shop.rating}</span>
                    </div>
                )}
            </div>
            
            <div className="p-4">
                <h2 className="text-xl font-bold text-gray-800 mb-2 line-clamp-2 group-hover:text-indigo-600 transition-colors">
                    {shop.name}
                </h2>
                
                <div className="flex items-center gap-2 mb-3">
                    {statusInfo && (
                        <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${statusInfo.class}`}>
                            {statusInfo.text}
                        </span>
                    )}
                    {shop.price_level && (
                        <span className="bg-blue-50 text-blue-700 text-xs font-semibold px-2.5 py-0.5 rounded-full">
                            {'$'.repeat(shop.price_level)}
                        </span>
                    )}
                    {shop.user_ratings_total > 0 && (
                        <span className="text-sm text-gray-500">
                            ({shop.user_ratings_total} reviews)
                        </span>
                    )}
                </div>
                
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
                    <span className="text-indigo-500 group-hover:translate-x-1 transition-transform inline-flex items-center">
                        View Details
                        <svg className="w-4 h-4 ml-1" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                        </svg>
                    </span>
                </div>
            </div>
        </div>
    );
}

export default CoffeeShopCard;
