// src/components/CoffeeShopCard.jsx
import React from 'react';

const CoffeeShopCard = ({ shop }) => {
    return (
        <div className="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition duration-300 border border-gray-100 cursor-pointer">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">{shop.name}</h2>
            
            <div className="flex items-center mb-3">
                <p className="text-sm text-indigo-600 font-semibold mr-2">
                    ⭐ {shop.rating || 'N/A'}
                </p>
                <p className="text-sm text-gray-500">
                    ({shop.user_ratings_total || 0} ulasan)
                </p>
            </div>
            
            <p className="text-gray-600 mb-4">{shop.address}</p>
            
            <div className="flex flex-wrap gap-2">
                {shop.business_status && (
                    <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${
                        shop.business_status === 'OPERATIONAL' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                        {shop.business_status === 'OPERATIONAL' ? 'Buka' : 'Tutup'}
                    </span>
                )}
                {shop.price_level && (
                    <span className="bg-blue-100 text-blue-700 text-xs font-semibold px-2.5 py-0.5 rounded-full">
                        {'💰'.repeat(shop.price_level)}
                    </span>
                )}
            </div>
            <p className="mt-4 text-indigo-500 font-medium">Klik untuk Detail & Review →</p>
        </div>
    );
}

export default CoffeeShopCard;