// SIMPLIFIED VERSION - Paste ini di ReviewList.jsx untuk ganti loadReviews function

const loadReviews = async (preserveExisting = false, forceRefresh = false) => {
  if (pendingRequestRef.current && !forceRefresh) {
    console.log('[ReviewList] Request already pending, skipping');
    return;
  }

  const now = Date.now();
  if (!forceRefresh && lastFetchTimeRef.current && (now - lastFetchTimeRef.current < 300)) {
    console.log('[ReviewList] Fetch cooldown active');
    return;
  }

  setLoading(true);
  setError(null);
  pendingRequestRef.current = true;

  try {
    console.log('[ReviewList] 🚀 Fetching reviews for:', placeId);
    const startTime = Date.now();

    // DIRECT QUERY - No complex Promise wrapping
    const { data, error } = await supabase
      .from('reviews')
      .select('id, user_id, place_id, rating, text, created_at, updated_at')
      .eq('place_id', placeId)
      .order('created_at', { ascending: false })
      .limit(25);

    const duration = Date.now() - startTime;
    console.log(`[ReviewList] ✅ Query completed in ${duration}ms`);

    if (error) {
      console.error('[ReviewList] ❌ Error:', error);
      setError('Gagal memuat reviews');
      if (!preserveExisting) setReviews([]);
      return;
    }

    if (!data || data.length === 0) {
      console.log('[ReviewList] No reviews found');
      setReviews([]);
      return;
    }

    // Fetch profiles
    const userIds = [...new Set(data.map(r => r.user_id))];
    const {data: profiles} = await supabase
      .from('profiles')
      .select('id, username, avatar_url, full_name')
      .in('id', userIds);

    const profilesMap = (profiles || []).reduce((acc, p) => {
      acc[p.id] = p;
      return acc;
    }, {});

    // Fetch photos
    const reviewIds = data.map(r => r.id);
    const {data: photos} = await supabase
      .from('review_photos')
      .select('id, review_id, photo_url')
      .in('review_id', reviewIds);

    const photosMap = (photos || []).reduce((acc, p) => {
      if (!acc[p.review_id]) acc[p.review_id] = [];
      acc[p.review_id].push(p);
      return acc;
    }, {});

    // Fetch replies
    const {data: replies} = await supabase
      .from('review_replies')
      .select('id, review_id, user_id, text, created_at, profiles:user_id(username, avatar_url, full_name)')
      .in('review_id', reviewIds);

    const repliesMap = (replies || []).reduce((acc, r) => {
      if (!acc[r.review_id]) acc[r.review_id] = [];
      acc[r.review_id].push(r);
      return acc;
    }, {});

    // Map reviews
    const mappedReviews = data.map(r => ({
      ...r,
      profiles: profilesMap[r.user_id] || null,
      photos: photosMap[r.id] || [],
      replies: repliesMap[r.id] || [],
      source: 'supabase'
    }));

    setReviews(mappedReviews);
    console.log(`[ReviewList] ✅ Set ${mappedReviews.length} reviews`);

  } catch (err) {
    console.error('[ReviewList] ❌ Exception:', err);
    setError('Terjadi kesalahan');
    if (!preserveExisting) setReviews([]);
  } finally {
    setLoading(false);
    pendingRequestRef.current = false;
    lastFetchTimeRef.current = Date.now();
  }
};

