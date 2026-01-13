import { useState } from 'react';
import { bulkUpdatePhotoUrls, verifyPhotoUrls } from '../utils/bulkPhotoUpdate';
import Navbar from '../components/Navbar';

export default function AdminPhotoUpdate() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);

  const handleBulkUpdate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await bulkUpdatePhotoUrls();
      setResult(res);
    } catch (err) {
      setError(err.message || 'Bulk update failed');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await verifyPhotoUrls();
      setVerifyResult(res);
    } catch (err) {
      setError(err.message || 'Verification failed');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-2xl mx-auto px-4">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">Admin: Photo URL Management</h1>

          {/* Buttons */}
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <div className="flex gap-4">
              <button
                onClick={handleBulkUpdate}
                disabled={loading}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition"
              >
                {loading ? 'Processing...' : 'Bulk Update Photo URLs'}
              </button>
              <button
                onClick={handleVerify}
                disabled={loading}
                className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition"
              >
                {loading ? 'Processing...' : 'Verify Photo URLs'}
              </button>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <h3 className="font-semibold text-red-900">Error:</h3>
              <p className="text-red-800">{error}</p>
            </div>
          )}

          {/* Bulk Update Result */}
          {result && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
              <h3 className="text-xl font-semibold text-green-900 mb-4">Bulk Update Complete ✅</h3>
              <div className="space-y-2 text-green-800">
                <p>✅ <strong>Updated:</strong> {result.updated}</p>
                <p>⏭️  <strong>Skipped:</strong> {result.skipped}</p>
                <p>📝 <strong>Total:</strong> {result.total}</p>
              </div>
            </div>
          )}

          {/* Verify Result */}
          {verifyResult && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h3 className="text-xl font-semibold text-blue-900 mb-4">Verification Results 📊</h3>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-white p-4 rounded border-l-4 border-green-500">
                  <p className="text-sm text-gray-600">Valid Supabase URLs</p>
                  <p className="text-2xl font-bold text-green-600">{verifyResult.validSupabaseUrl}</p>
                </div>
                <div className="bg-white p-4 rounded border-l-4 border-yellow-500">
                  <p className="text-sm text-gray-600">Invalid URLs</p>
                  <p className="text-2xl font-bold text-yellow-600">{verifyResult.invalidUrl}</p>
                </div>
                <div className="bg-white p-4 rounded border-l-4 border-red-500">
                  <p className="text-sm text-gray-600">Missing URLs</p>
                  <p className="text-2xl font-bold text-red-600">{verifyResult.withoutUrl}</p>
                </div>
                <div className="bg-white p-4 rounded border-l-4 border-blue-500">
                  <p className="text-sm text-gray-600">Total</p>
                  <p className="text-2xl font-bold text-blue-600">{verifyResult.total}</p>
                </div>
              </div>

              {/* Details */}
              {verifyResult.details && verifyResult.details.length > 0 && (
                <details className="mb-4">
                  <summary className="cursor-pointer font-semibold text-blue-900 hover:text-blue-700">
                    View Details ({verifyResult.details.length} items)
                  </summary>
                  <div className="mt-4 space-y-2 text-sm">
                    {verifyResult.details.map((item, idx) => (
                      <div key={idx} className="bg-white p-3 rounded border">
                        <p className="font-mono text-xs text-gray-600">{item.place_id}</p>
                        <p className="font-semibold text-gray-900">{item.name}</p>
                        <p className={`text-xs font-semibold ${
                          item.status === 'VALID' ? 'text-green-600' : 
                          item.status === 'MISSING' ? 'text-red-600' : 
                          'text-yellow-600'
                        }`}>
                          {item.status}
                        </p>
                        {item.url && (
                          <p className="text-xs text-gray-500 mt-1 break-all">{item.url}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}

          {/* Info Box */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-6">
            <p className="text-sm text-blue-800">
              <strong>Template URL:</strong>
              <br />
              <code className="bg-white px-2 py-1 rounded block mt-2 font-mono text-xs">
              https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/[place_id].webp
              </code>
            </p>
          </div>
        </div>
      </main>
    </>
  );
}
