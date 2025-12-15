/**
 * Utility untuk mapping keywords dan stop words
 * - Stop words: kata-kata yang diabaikan saat analisis
 * - Sinonim mapping: mapping kata-kata ke sinonimnya untuk normalisasi
 */

/**
 * Daftar stop words (kata-kata yang tidak perlu dianalisis)
 * Kata-kata ini akan diabaikan saat ekstraksi keywords
 */
export const STOP_WORDS = new Set([
  // Kata ganti
  'saya', 'aku', 'gue', 'gw', 'saya', 'kamu', 'anda', 'engkau', 'kau', 'dia', 'ia',
  'kami', 'kita', 'mereka', 'kalian',
  
  // Kata kerja umum
  'ingin', 'mau', 'hendak', 'akan', 'mencari', 'cari', 'butuh', 'perlu', 'butuhkan',
  'menginginkan', 'menginginkan', 'inginkan',
  
  // Kata sambung
  'yang', 'dan', 'atau', 'serta', 'juga', 'lagi', 'pula',
  
  // Kata depan
  'di', 'ke', 'dari', 'pada', 'untuk', 'dengan', 'oleh', 'dari', 'kepada', 'terhadap',
  'antara', 'dalam', 'atas', 'bawah', 'depan', 'belakang',
  
  // Kata sifat umum
  'sangat', 'sekali', 'amat', 'terlalu', 'cukup', 'agak', 'sedikit', 'banyak',
  
  // Kata keterangan
  'sudah', 'belum', 'akan', 'telah', 'sedang', 'masih', 'pernah', 'tidak', 'tak',
  'bukan', 'jika', 'kalau', 'karena', 'sebab', 'jadi', 'maka', 'adalah', 'ialah',
  
  // Kata umum lainnya
  'ada', 'ini', 'itu', 'tersebut', 'begitu', 'demikian', 'seperti', 'bagai',
  'tempat', 'lokasi', 'area', 'daerah', 'zona',
  
  // Kata terkait coffee shop (generic)
  'coffee shop', 'coffeeshop', 'cafe', 'kafe', 'kedai', 'warung', 'toko',
  'restoran', 'restaurant', 'tempat makan', 'tempat minum',
  
  // Kata bahasa Inggris umum
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
  'can', 'may', 'might', 'must', 'shall',
  
  // Kata tambahan
  'dll', 'dsb', 'dkk', 'dll', 'dan lain lain', 'dan sebagainya',
  'yang', 'untuk', 'dengan', 'dari', 'pada', 'oleh',
]);

/**
 * Mapping sinonim untuk normalisasi kata
 * Key: kata utama (akan dinormalisasi ke sini)
 * Value: array of sinonim (termasuk variasi ejaan, slang, dll)
 */
export const SYNONYM_MAPPING = {
  // Kata ganti orang pertama
  'saya': ['aku', 'gue', 'gw', 'saya'],
  'aku': ['saya', 'gue', 'gw'],
  
  // Coffee shop / tempat
  'coffee shop': ['kopi sop', 'warkop', 'tempat nongkrong', 'tempat', 'cafe', 'kafe', 'kedai kopi', 'warung kopi', 'coffeeshop'],
  'cafe': ['coffee shop', 'kopi sop', 'warkop', 'tempat nongkrong', 'kafe', 'kedai kopi', 'warung kopi'],
  'kafe': ['coffee shop', 'cafe', 'kopi sop', 'warkop', 'tempat nongkrong', 'kedai kopi', 'warung kopi'],
  'warkop': ['coffee shop', 'cafe', 'kafe', 'kopi sop', 'tempat nongkrong', 'warung kopi', 'kedai kopi'],
  'tempat nongkrong': ['coffee shop', 'cafe', 'kafe', 'warkop', 'kopi sop', 'tempat', 'warung kopi'],
  'tempat': ['coffee shop', 'cafe', 'kafe', 'warkop', 'tempat nongkrong', 'lokasi', 'area'],
  
  // Ingin / mau
  'ingin': ['mau', 'hendak', 'mencari', 'cari', 'butuh', 'perlu', 'butuhkan'],
  'mau': ['ingin', 'hendak', 'mencari', 'cari', 'butuh', 'perlu'],
  'mencari': ['cari', 'ingin', 'mau', 'butuh', 'perlu'],
  'cari': ['mencari', 'ingin', 'mau', 'butuh', 'perlu'],
  
  // WiFi
  'wifi': ['wifi', 'wi-fi', 'internet', 'koneksi', 'jaringan'],
  'wifi bagus': ['wifi kencang', 'wifi stabil', 'wifi cepat', 'internet kencang', 'koneksi lancar'],
  'wifi kencang': ['wifi bagus', 'wifi stabil', 'wifi cepat', 'internet kencang'],
  
  // Colokan / terminal
  'colokan': ['terminal', 'stopkontak', 'soket', 'outlet', 'colokan listrik'],
  'terminal': ['colokan', 'stopkontak', 'soket', 'outlet', 'colokan listrik'],
  'stopkontak': ['colokan', 'terminal', 'soket', 'outlet'],
  
  // Nyaman / cozy (termasuk suasana tenang)
  'nyaman': ['cozy', 'comfortable', 'enak', 'betah', 'asik', 'tenang', 'sunyi', 'sepi', 'hangat', 'asri'],
  'cozy': ['nyaman', 'comfortable', 'enak', 'betah', 'asik', 'tenang', 'sunyi', 'sepi', 'hangat', 'asri', 'relaks'],
  'comfortable': ['nyaman', 'cozy', 'enak', 'betah', 'asik'],
  'enak': ['nyaman', 'cozy', 'comfortable', 'betah', 'asik'],
  'betah': ['nyaman', 'cozy', 'comfortable', 'enak', 'asik'],
  'asik': ['nyaman', 'cozy', 'comfortable', 'enak', 'betah'],
  
  // Tenang (termasuk suasana nyaman)
  'tenang': ['sunyi', 'sepi', 'quiet', 'silent', 'tidak ramai', 'nyaman', 'cozy', 'relaks', 'peaceful'],
  'sunyi': ['tenang', 'sepi', 'quiet', 'silent', 'nyaman', 'cozy'],
  'sepi': ['tenang', 'sunyi', 'quiet', 'silent', 'tidak ramai'],
  'relaks': ['tenang', 'nyaman', 'cozy', 'santai', 'rileks'],
  'santai': ['relaks', 'tenang', 'nyaman', 'cozy', 'rileks'],
  
  // Dingin / AC
  'dingin': ['sejuk', 'adem', 'ac', 'air conditioner', 'pendingin'],
  'sejuk': ['dingin', 'adem', 'ac'],
  'ac': ['air conditioner', 'pendingin', 'dingin', 'sejuk'],
  
  // Parkir
  'parkir': ['parkiran', 'tempat parkir', 'parking', 'area parkir'],
  'parkiran': ['parkir', 'tempat parkir', 'parking'],
  
  // Musholla
  'musholla': ['mushola', 'tempat sholat', 'ruang sholat', 'tempat ibadah'],
  'mushola': ['musholla', 'tempat sholat', 'ruang sholat'],
  
  // Belajar / kerja
  'belajar': ['study', 'ngerjain tugas', 'mengerjakan tugas', 'kuliah', 'kerja'],
  'kerja': ['bekerja', 'work', 'wfh', 'work from home', 'remote work'],
  'wfh': ['work from home', 'kerja', 'remote work'],
  
  // Live music
  'live music': ['musik live', 'akustik', 'pertunjukan musik', 'musik', 'hiburan musik'],
  'akustik': ['live music', 'musik akustik', 'pertunjukan akustik'],
  
  // 24 jam
  '24 jam': ['buka 24 jam', 'buka sampai larut', 'larut malam', 'buka malam', 'buka sampai subuh'],
  'buka malam': ['24 jam', 'buka sampai larut', 'larut malam', 'buka sampai subuh'],
  
  // Aesthetic
  'aesthetic': ['estetik', 'kekinian', 'instagramable', 'fotogenic', 'bagus'],
  'estetik': ['aesthetic', 'kekinian', 'instagramable'],
  
  // Harga
  'murah': ['terjangkau', 'harga murah', 'harga terjangkau', 'affordable', 'budget friendly'],
  'terjangkau': ['murah', 'harga murah', 'harga terjangkau'],
};

/**
 * Normalisasi kata menggunakan mapping sinonim
 * @param {string} word - Kata yang akan dinormalisasi
 * @returns {string} Kata yang sudah dinormalisasi (atau kata asli jika tidak ada mapping)
 */
export function normalizeWord(word) {
  if (!word) return '';
  
  const wordLower = word.toLowerCase().trim();
  
  // Cek apakah kata ada di mapping (sebagai key)
  if (SYNONYM_MAPPING[wordLower]) {
    return wordLower; // Return key utama
  }
  
  // Cek apakah kata ada di value (sinonim)
  for (const [key, synonyms] of Object.entries(SYNONYM_MAPPING)) {
    if (synonyms.includes(wordLower)) {
      return key; // Return key utama
    }
  }
  
  // Jika tidak ada mapping, return kata asli
  return wordLower;
}

/**
 * Cek apakah kata adalah stop word
 * @param {string} word - Kata yang akan dicek
 * @returns {boolean} True jika stop word, false jika bukan
 */
export function isStopWord(word) {
  if (!word) return true;
  
  const wordLower = word.toLowerCase().trim();
  
  // Cek exact match
  if (STOP_WORDS.has(wordLower)) {
    return true;
  }
  
  // Cek apakah kata mengandung stop word (untuk multi-word seperti "coffee shop")
  for (const stopWord of STOP_WORDS) {
    if (wordLower.includes(stopWord) || stopWord.includes(wordLower)) {
      return true;
    }
  }
  
  return false;
}

/**
 * Filter stop words dari array kata
 * @param {Array<string>} words - Array of words
 * @returns {Array<string>} Array of words tanpa stop words
 */
export function filterStopWords(words) {
  if (!Array.isArray(words)) return [];
  
  return words
    .map(word => word.trim().toLowerCase())
    .filter(word => word.length > 0 && !isStopWord(word));
}

/**
 * Normalisasi dan filter keywords
 * @param {Array<string>} keywords - Array of keywords
 * @returns {Array<string>} Array of normalized keywords tanpa stop words
 */
export function normalizeAndFilterKeywords(keywords) {
  if (!Array.isArray(keywords)) return [];
  
  return keywords
    .map(keyword => keyword.trim().toLowerCase())
    .filter(keyword => keyword.length > 0 && !isStopWord(keyword))
    .map(keyword => normalizeWord(keyword))
    .filter((keyword, index, self) => self.indexOf(keyword) === index); // Remove duplicates
}

/**
 * Ekstrak keywords dari text dengan filter stop words dan normalisasi
 * @param {string} text - Text yang akan diekstrak keywords-nya
 * @returns {Array<string>} Array of normalized keywords
 */
export function extractKeywordsFromText(text) {
  if (!text || typeof text !== 'string') return [];
  
  // Split menjadi words
  const words = text
    .split(/\s+|,/)
    .map(word => word.replace(/[^\w\s]/g, '').trim())
    .filter(word => word.length >= 2);
  
  // Filter stop words dan normalisasi
  return normalizeAndFilterKeywords(words);
}

/**
 * Expand keyword dengan sinonimnya
 * @param {string} keyword - Keyword yang akan di-expand
 * @returns {Array<string>} Array of keywords (original + synonyms)
 */
export function expandKeywordWithSynonyms(keyword) {
  if (!keyword) return [];
  
  const normalized = normalizeWord(keyword);
  const synonyms = SYNONYM_MAPPING[normalized] || [];
  
  // Return original + synonyms (unique)
  return [normalized, ...synonyms].filter((v, i, self) => self.indexOf(v) === i);
}

