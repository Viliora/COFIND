import { describe, it, expect } from 'vitest'
import {
  getPersonalizedRecommendations,
  getPersonalizedRecommendationsWithReasons,
} from './personalizedRecommendations'

const baseShop = (overrides = {}) => ({
  place_id: 'p1',
  name: 'Kopi A',
  address: 'Jl. Contoh',
  rating: '4.5',
  location: { lat: -6.2, lng: 106.8 },
  ...overrides,
})

describe('personalizedRecommendations', () => {
  describe('getPersonalizedRecommendations', () => {
    it('mengembalikan kosong tanpa favorit', () => {
      expect(getPersonalizedRecommendations([], [baseShop()])).toEqual([])
      expect(getPersonalizedRecommendations(null, [baseShop()])).toEqual([])
    })

    it('mengembalikan kosong tanpa katalog toko', () => {
      const fav = [baseShop({ place_id: 'f1' })]
      expect(getPersonalizedRecommendations(fav, [])).toEqual([])
      expect(getPersonalizedRecommendations(fav, null)).toEqual([])
    })

    it('menyembunyikan favorit ketika excludeFavorites true', () => {
      const fav = [baseShop({ place_id: 'f1', name: 'Favorit Saya' })]
      const all = [
        fav[0],
        baseShop({ place_id: 'p2', name: 'Lain', rating: '4.8' }),
      ]
      const rec = getPersonalizedRecommendations(fav, all, { maxResults: 5 })
      expect(rec.every((s) => s.place_id !== 'f1')).toBe(true)
      expect(rec.length).toBeGreaterThan(0)
    })

    it('memfilter rating di bawah minRating', () => {
      const fav = [baseShop({ place_id: 'f1' })]
      const all = [
        baseShop({ place_id: 'p2', name: 'Rendah', rating: '3.0' }),
        baseShop({ place_id: 'p3', name: 'Tinggi', rating: '4.9' }),
      ]
      const rec = getPersonalizedRecommendations(fav, all, {
        minRating: 4.0,
        maxResults: 10,
      })
      expect(rec.map((s) => s.place_id)).toEqual(['p3'])
    })

    it('membatasi jumlah hasil dengan maxResults', () => {
      const fav = [baseShop({ place_id: 'f1' })]
      const all = Array.from({ length: 15 }, (_, i) =>
        baseShop({
          place_id: `p${i + 2}`,
          name: `Toko ${i}`,
          rating: '4.5',
        })
      )
      const rec = getPersonalizedRecommendations(fav, all, { maxResults: 3 })
      expect(rec.length).toBe(3)
    })

    it('menyertakan skor rekomendasi dan mengurutkan menurun', () => {
      const fav = [
        baseShop({
          place_id: 'f1',
          name: 'Warkop Senayan',
          address: 'Jakarta',
          location: { lat: -6.2, lng: 106.8 },
        }),
      ]
      const all = [
        baseShop({
          place_id: 'p2',
          name: 'Warung Kopi Beta',
          address: 'Jakarta Pusat',
          rating: '4.6',
          location: { lat: -6.21, lng: 106.81 },
        }),
        baseShop({
          place_id: 'p3',
          name: 'Sushi Bar',
          address: 'Tokyo',
          rating: '4.9',
          location: { lat: 35.0, lng: 139.0 },
        }),
      ]
      const rec = getPersonalizedRecommendations(fav, all, { maxResults: 5 })
      expect(rec[0].recommendationScore).toBeGreaterThanOrEqual(
        rec[rec.length - 1].recommendationScore
      )
      expect(rec[0]).toHaveProperty('contextSimilarity')
      expect(rec[0]).toHaveProperty('ratingScore')
      expect(rec[0]).toHaveProperty('locationScore')
    })
  })

  describe('getPersonalizedRecommendationsWithReasons', () => {
    it('menambahkan reasons pada setiap item', () => {
      const fav = [baseShop({ place_id: 'f1' })]
      const all = [
        baseShop({ place_id: 'p2', rating: '4.9', name: 'High Rating Cafe' }),
      ]
      const withReasons = getPersonalizedRecommendationsWithReasons(fav, all, {
        maxResults: 5,
      })
      expect(withReasons.length).toBeGreaterThan(0)
      expect(Array.isArray(withReasons[0].reasons)).toBe(true)
      expect(withReasons[0].reasons.length).toBeGreaterThan(0)
    })
  })
})
