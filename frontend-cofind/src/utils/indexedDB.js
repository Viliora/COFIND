// IndexedDB Utility untuk menyimpan data kompleks di browser
// Digunakan untuk cache data yang lebih besar dan kompleks

const DB_NAME = 'cofind-db';
const DB_VERSION = 1;
const STORE_NAMES = {
  COFFEE_SHOPS: 'coffeeShops',
  FAVORITES: 'favorites',
  SEARCH_HISTORY: 'searchHistory',
  USER_DATA: 'userData',
};

let dbInstance = null;

/**
 * Membuka koneksi ke IndexedDB
 * @returns {Promise<IDBDatabase>}
 */
export async function openDB() {
  if (dbInstance) {
    return dbInstance;
  }

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => {
      console.error('[IndexedDB] Error opening database:', request.error);
      reject(request.error);
    };

    request.onsuccess = () => {
      dbInstance = request.result;
      console.log('[IndexedDB] Database opened successfully');
      resolve(dbInstance);
    };

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      
      // Create object stores jika belum ada
      if (!db.objectStoreNames.contains(STORE_NAMES.COFFEE_SHOPS)) {
        const coffeeShopsStore = db.createObjectStore(STORE_NAMES.COFFEE_SHOPS, {
          keyPath: 'place_id',
        });
        coffeeShopsStore.createIndex('name', 'name', { unique: false });
        coffeeShopsStore.createIndex('rating', 'rating', { unique: false });
      }

      if (!db.objectStoreNames.contains(STORE_NAMES.FAVORITES)) {
        const favoritesStore = db.createObjectStore(STORE_NAMES.FAVORITES, {
          keyPath: 'place_id',
        });
        favoritesStore.createIndex('addedAt', 'addedAt', { unique: false });
      }

      if (!db.objectStoreNames.contains(STORE_NAMES.SEARCH_HISTORY)) {
        const searchHistoryStore = db.createObjectStore(STORE_NAMES.SEARCH_HISTORY, {
          keyPath: 'id',
          autoIncrement: true,
        });
        searchHistoryStore.createIndex('timestamp', 'timestamp', { unique: false });
      }

      if (!db.objectStoreNames.contains(STORE_NAMES.USER_DATA)) {
        db.createObjectStore(STORE_NAMES.USER_DATA, {
          keyPath: 'key',
        });
      }

      console.log('[IndexedDB] Database upgraded');
    };
  });
}

/**
 * Menyimpan data ke IndexedDB
 * @param {string} storeName - Nama object store
 * @param {any} data - Data yang akan disimpan
 * @returns {Promise<void>}
 */
export async function saveToDB(storeName, data) {
  try {
    const db = await openDB();
    const transaction = db.transaction([storeName], 'readwrite');
    const store = transaction.objectStore(storeName);

    // Jika data adalah array, simpan semua item
    if (Array.isArray(data)) {
      await Promise.all(data.map(item => {
        return new Promise((resolve, reject) => {
          const request = store.put(item);
          request.onsuccess = () => resolve();
          request.onerror = () => reject(request.error);
        });
      }));
    } else {
      await new Promise((resolve, reject) => {
        const request = store.put(data);
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      });
    }

    console.log('[IndexedDB] Data saved to', storeName);
  } catch (error) {
    console.error('[IndexedDB] Error saving data:', error);
    throw error;
  }
}

/**
 * Mengambil data dari IndexedDB
 * @param {string} storeName - Nama object store
 * @param {string|number|null} key - Key untuk mengambil data spesifik, atau null untuk semua
 * @returns {Promise<any>}
 */
export async function getFromDB(storeName, key = null) {
  try {
    const db = await openDB();
    const transaction = db.transaction([storeName], 'readonly');
    const store = transaction.objectStore(storeName);

    if (key === null) {
      // Ambil semua data
      return new Promise((resolve, reject) => {
        const request = store.getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
    } else {
      // Ambil data spesifik
      return new Promise((resolve, reject) => {
        const request = store.get(key);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
        request.onerror = () => resolve(null); // Return null jika tidak ditemukan
      });
    }
  } catch (error) {
    console.error('[IndexedDB] Error getting data:', error);
    return null;
  }
}

/**
 * Menghapus data dari IndexedDB
 * @param {string} storeName - Nama object store
 * @param {string|number} key - Key dari data yang akan dihapus
 * @returns {Promise<void>}
 */
export async function deleteFromDB(storeName, key) {
  try {
    const db = await openDB();
    const transaction = db.transaction([storeName], 'readwrite');
    const store = transaction.objectStore(storeName);

    await new Promise((resolve, reject) => {
      const request = store.delete(key);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });

    console.log('[IndexedDB] Data deleted from', storeName);
  } catch (error) {
    console.error('[IndexedDB] Error deleting data:', error);
    throw error;
  }
}

/**
 * Menghapus semua data dari object store
 * @param {string} storeName - Nama object store
 * @returns {Promise<void>}
 */
export async function clearStore(storeName) {
  try {
    const db = await openDB();
    const transaction = db.transaction([storeName], 'readwrite');
    const store = transaction.objectStore(storeName);

    await new Promise((resolve, reject) => {
      const request = store.clear();
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });

    console.log('[IndexedDB] Store cleared:', storeName);
  } catch (error) {
    console.error('[IndexedDB] Error clearing store:', error);
    throw error;
  }
}

/**
 * Menghapus seluruh database
 * @returns {Promise<void>}
 */
export async function deleteDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = () => {
      dbInstance = null;
      console.log('[IndexedDB] Database deleted');
      resolve();
    };
    request.onerror = () => {
      console.error('[IndexedDB] Error deleting database:', request.error);
      reject(request.error);
    };
  });
}

/**
 * Helper functions untuk coffee shops
 */
export const coffeeShopsDB = {
  async save(data) {
    return saveToDB(STORE_NAMES.COFFEE_SHOPS, data);
  },
  
  async get(key = null) {
    return getFromDB(STORE_NAMES.COFFEE_SHOPS, key);
  },
  
  async delete(key) {
    return deleteFromDB(STORE_NAMES.COFFEE_SHOPS, key);
  },
  
  async clear() {
    return clearStore(STORE_NAMES.COFFEE_SHOPS);
  },
};

/**
 * Helper functions untuk favorites
 */
export const favoritesDB = {
  async save(favorite) {
    const data = {
      ...favorite,
      addedAt: new Date().toISOString(),
    };
    return saveToDB(STORE_NAMES.FAVORITES, data);
  },
  
  async getAll() {
    return getFromDB(STORE_NAMES.FAVORITES);
  },
  
  async get(placeId) {
    return getFromDB(STORE_NAMES.FAVORITES, placeId);
  },
  
  async delete(placeId) {
    return deleteFromDB(STORE_NAMES.FAVORITES, placeId);
  },
  
  async clear() {
    return clearStore(STORE_NAMES.FAVORITES);
  },
};

/**
 * Helper functions untuk search history
 */
export const searchHistoryDB = {
  async save(searchTerm) {
    const data = {
      term: searchTerm,
      timestamp: Date.now(),
    };
    return saveToDB(STORE_NAMES.SEARCH_HISTORY, data);
  },
  
  async getAll() {
    return getFromDB(STORE_NAMES.SEARCH_HISTORY);
  },
  
  async clear() {
    return clearStore(STORE_NAMES.SEARCH_HISTORY);
  },
};

// Export store names untuk reference
export { STORE_NAMES };

// Default export
export default {
  openDB,
  saveToDB,
  getFromDB,
  deleteFromDB,
  clearStore,
  deleteDB,
  coffeeShopsDB,
  favoritesDB,
  searchHistoryDB,
  STORE_NAMES,
};

