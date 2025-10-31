import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import SearchBar from '../components/SearchBar';
import CoffeeShopCard from '../components/CoffeeShopCard';

export default function ShopList() {
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';
  const [coffeeShops, setCoffeeShops] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState(null);
  const scrollContainerRef = useRef(null);

  const scrollRight = () => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const scrollAmount = container.clientWidth * 0.8;
    container.scrollBy({ left: scrollAmount, behavior: 'smooth' });
  };

  useEffect(() => {
    const fetchShops = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const response = await fetch(`${API_BASE}/api/search/coffeeshops?lat=-0.026330&lng=109.342506`);
        const result = await response.json();

        if (!response.ok) {
          throw new Error(result.message || `Error fetching data (${response.status})`);
        }

        if (result.status === 'success' && Array.isArray(result.data)) {
          setCoffeeShops(result.data);
        } else {
          throw new Error(result.message || 'Invalid data format received');
        }
      } catch (err) {
        console.error("Error fetching data:", err);
        setError(err.message || "Failed to fetch coffee shop data");
        setCoffeeShops([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchShops();
  }, [API_BASE]);

  const filteredShops = coffeeShops.filter(shop =>
    shop.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="text-center p-16">
        <h1 className="text-3xl text-indigo-600 font-semibold">Loading Coffee Shops in Pontianak...</h1>
        <div className="mt-4 flex justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <div className="bg-indigo-700 h-40 flex items-center justify-center text-white mb-6 rounded-lg shadow-lg">
        <h1 className="text-4xl font-extrabold tracking-tight">Temukan Coffee Shop Terbaik di Pontianak</h1>
      </div>

      <SearchBar setSearchTerm={setSearchTerm} />

      <main className="max-w-4xl mx-auto py-8">
        <h2 className="text-3xl font-bold text-gray-800 mb-6 border-b pb-2">
          Coffee Shop Catalog ({filteredShops.length} found)
          {searchTerm && <span className="text-gray-500 text-lg"> - Search: "{searchTerm}"</span>}
        </h2>

        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-6">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Error loading data</h3>
                <p className="mt-1 text-sm text-red-700">{error}</p>
                <button
                  onClick={() => window.location.reload()}
                  className="mt-2 text-sm text-red-600 hover:text-red-500 font-medium"
                >
                  Try Again → 
                </button>
              </div>
            </div>
          </div>
        )}

        {!error && filteredShops.length > 0 && (
          <div className="relative">
            <div
              ref={scrollContainerRef}
              className="flex gap-6 overflow-x-auto scroll-smooth pb-4 pr-16 snap-x snap-mandatory"
            >
              {filteredShops.map((shop) => (
                <Link
                  key={shop.place_id}
                  to={`/shop/${shop.place_id}`}
                  className="block hover:shadow-2xl transition duration-300 min-w-[260px] sm:min-w-[300px] shrink-0 snap-start"
                >
                  <CoffeeShopCard shop={shop} />
                </Link>
              ))}
            </div>

            <button
              type="button"
              onClick={scrollRight}
              className="absolute right-0 top-1/2 -translate-y-1/2 bg-indigo-600 text-white p-3 rounded-full shadow-lg hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              aria-label="Scroll ke kanan"
            >
              →
            </button>
          </div>
        )}

        {!error && !isLoading && filteredShops.length === 0 && searchTerm === '' && (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 20a8 8 0 100-16 8 8 0 000 16z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No coffee shops found</h3>
            <p className="mt-1 text-sm text-gray-500">Check if the backend is returning data correctly.</p>
          </div>
        )}
        {!error && !isLoading && filteredShops.length === 0 && searchTerm !== '' && (
          <div className="text-center py-12">
            <h3 className="text-lg font-medium text-gray-900">No results for "{searchTerm}"</h3>
            <p className="mt-2 text-gray-500">Try different search terms or clear the search.</p>
            <button
              onClick={() => setSearchTerm('')}
              className="mt-4 text-indigo-600 hover:text-indigo-500"
            >
              Clear Search
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
