// src/components/CoffeeShopCard.jsx
import React from 'react';

const CoffeeShopCard = ({ shop }) => {
    return (
        <div className="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition duration-300 border border-gray-100 cursor-pointer">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">{shop.nama} (ID: {shop.id})</h2>
            
            <p className="text-sm text-indigo-600 font-semibold mb-3">
                ⭐ {shop.rating} / 5.0
            </p>
            
            <p className="text-gray-600 mb-4">{shop.alamat}</p>
            
            <div className="flex flex-wrap gap-2">
                <span className="text-sm font-medium text-gray-700 mr-2">Fitur Utama (LLaMA):</span>
                {shop.tags_llm.map(tag => (
                    <span 
                        key={tag} 
                        className="bg-green-100 text-green-700 text-xs font-semibold px-2.5 py-0.5 rounded-full"
                    >
                        {tag.replace('_', ' ')}
                    </span>
                ))}
            </div>
            <p className="mt-4 text-indigo-500 font-medium">Klik untuk Detail & Review →</p>
        </div>
    );
}

export default CoffeeShopCard;