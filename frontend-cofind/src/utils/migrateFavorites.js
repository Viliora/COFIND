import { supabase, isSupabaseConfigured } from '../lib/supabase';

/**
 * Migrate localStorage favorites and want-to-visit to Supabase
 * This should be called once when user logs in for the first time
 */
export const migrateLocalStorageToSupabase = async (userId) => {
  if (!isSupabaseConfigured || !supabase || !userId) {
    console.log('[Migration] Skipped: Supabase not configured or no user');
    return { success: false, error: 'Not configured' };
  }

  try {
    const results = {
      favorites: { migrated: 0, skipped: 0, errors: 0 },
      wantToVisit: { migrated: 0, skipped: 0, errors: 0 }
    };

    // Check if already migrated
    const migrationKey = `cofind_migrated_${userId}`;
    if (localStorage.getItem(migrationKey)) {
      console.log('[Migration] Already migrated for this user');
      return { success: true, alreadyMigrated: true };
    }

    // Migrate favorites
    const favorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
    if (favorites.length > 0) {
      console.log(`[Migration] Migrating ${favorites.length} favorites...`);
      
      for (const placeId of favorites) {
        try {
          const { error } = await supabase
            .from('favorites')
            .upsert({ user_id: userId, place_id: placeId }, {
              onConflict: 'user_id,place_id'
            });
          
          if (error) {
            if (error.code === '23505') { // Duplicate
              results.favorites.skipped++;
            } else {
              results.favorites.errors++;
              console.error('[Migration] Favorite error:', error);
            }
          } else {
            results.favorites.migrated++;
          }
        } catch {
          results.favorites.errors++;
        }
      }
    }

    // Migrate want-to-visit
    const wantToVisit = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
    if (wantToVisit.length > 0) {
      console.log(`[Migration] Migrating ${wantToVisit.length} want-to-visit...`);
      
      for (const placeId of wantToVisit) {
        try {
          const { error } = await supabase
            .from('want_to_visit')
            .upsert({ user_id: userId, place_id: placeId }, {
              onConflict: 'user_id,place_id'
            });
          
          if (error) {
            if (error.code === '23505') { // Duplicate
              results.wantToVisit.skipped++;
            } else {
              results.wantToVisit.errors++;
              console.error('[Migration] Want-to-visit error:', error);
            }
          } else {
            results.wantToVisit.migrated++;
          }
        } catch {
          results.wantToVisit.errors++;
        }
      }
    }

    // Mark as migrated
    localStorage.setItem(migrationKey, 'true');

    console.log('[Migration] Complete:', results);
    return { success: true, results };

  } catch (err) {
    console.error('[Migration] Failed:', err);
    return { success: false, error: err.message };
  }
};

/**
 * Get favorites for current user (from Supabase or localStorage fallback)
 */
export const getFavorites = async (userId) => {
  if (!isSupabaseConfigured || !supabase) {
    // Fallback to localStorage
    return JSON.parse(localStorage.getItem('favoriteShops') || '[]');
  }

  if (!userId) {
    return JSON.parse(localStorage.getItem('favoriteShops') || '[]');
  }

  try {
    const { data, error } = await supabase
      .from('favorites')
      .select('place_id')
      .eq('user_id', userId);

    if (error) throw error;
    return data.map(f => f.place_id);
  } catch (err) {
    console.error('[Favorites] Error fetching:', err);
    return JSON.parse(localStorage.getItem('favoriteShops') || '[]');
  }
};

/**
 * Toggle favorite status
 */
export const toggleFavorite = async (userId, placeId) => {
  // Always update localStorage for guests
  const localFavorites = JSON.parse(localStorage.getItem('favoriteShops') || '[]');
  const isCurrentlyFavorite = localFavorites.includes(placeId);

  if (isCurrentlyFavorite) {
    const updated = localFavorites.filter(id => id !== placeId);
    localStorage.setItem('favoriteShops', JSON.stringify(updated));
  } else {
    localFavorites.push(placeId);
    localStorage.setItem('favoriteShops', JSON.stringify(localFavorites));
  }

  // Also update Supabase if logged in
  if (isSupabaseConfigured && supabase && userId) {
    try {
      if (isCurrentlyFavorite) {
        await supabase
          .from('favorites')
          .delete()
          .eq('user_id', userId)
          .eq('place_id', placeId);
      } else {
        await supabase
          .from('favorites')
          .insert({ user_id: userId, place_id: placeId });
      }
    } catch (err) {
      console.error('[Favorites] Toggle error:', err);
    }
  }

  return !isCurrentlyFavorite;
};

/**
 * Get want-to-visit for current user
 */
export const getWantToVisit = async (userId) => {
  if (!isSupabaseConfigured || !supabase) {
    return JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
  }

  if (!userId) {
    return JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
  }

  try {
    const { data, error } = await supabase
      .from('want_to_visit')
      .select('place_id')
      .eq('user_id', userId);

    if (error) throw error;
    return data.map(w => w.place_id);
  } catch (err) {
    console.error('[WantToVisit] Error fetching:', err);
    return JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
  }
};

/**
 * Toggle want-to-visit status
 */
export const toggleWantToVisit = async (userId, placeId) => {
  // Always update localStorage for guests
  const localWtv = JSON.parse(localStorage.getItem('wantToVisitShops') || '[]');
  const isCurrentlyWtv = localWtv.includes(placeId);

  if (isCurrentlyWtv) {
    const updated = localWtv.filter(id => id !== placeId);
    localStorage.setItem('wantToVisitShops', JSON.stringify(updated));
  } else {
    localWtv.push(placeId);
    localStorage.setItem('wantToVisitShops', JSON.stringify(localWtv));
  }

  // Also update Supabase if logged in
  if (isSupabaseConfigured && supabase && userId) {
    try {
      if (isCurrentlyWtv) {
        await supabase
          .from('want_to_visit')
          .delete()
          .eq('user_id', userId)
          .eq('place_id', placeId);
      } else {
        await supabase
          .from('want_to_visit')
          .insert({ user_id: userId, place_id: placeId });
      }
    } catch (err) {
      console.error('[WantToVisit] Toggle error:', err);
    }
  }

  return !isCurrentlyWtv;
};
