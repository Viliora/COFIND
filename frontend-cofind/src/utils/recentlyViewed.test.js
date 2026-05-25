import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  addToRecentlyViewed,
  getRecentlyViewed,
  clearRecentlyViewed,
  removeFromRecentlyViewed,
  getRecentlyViewedWithDetails,
} from './recentlyViewed'

const store = {}

beforeEach(() => {
  Object.keys(store).forEach((k) => delete store[k])
  const ls = {
    getItem: vi.fn((k) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null)),
    setItem: vi.fn((k, v) => {
      store[k] = v
    }),
    removeItem: vi.fn((k) => {
      delete store[k]
    }),
  }
  vi.stubGlobal('localStorage', ls)
})

describe('recentlyViewed', () => {
  it('menolak shop tanpa place_id atau name', () => {
    addToRecentlyViewed(null)
    addToRecentlyViewed({ place_id: 'x' })
    expect(getRecentlyViewed()).toEqual([])
  })

  it('menambah, membatasi jumlah, dan membaca kembali', () => {
    for (let i = 0; i < 12; i += 1) {
      addToRecentlyViewed({ place_id: `p${i}`, name: `Toko ${i}` })
    }
    const all = getRecentlyViewed()
    expect(all.length).toBe(10)
    expect(all[0].place_id).toBe('p11')
  })

  it('clearRecentlyViewed mengosongkan', () => {
    addToRecentlyViewed({ place_id: 'a', name: 'A' })
    clearRecentlyViewed()
    expect(getRecentlyViewed()).toEqual([])
  })

  it('removeFromRecentlyViewed menghapus satu place_id', () => {
    addToRecentlyViewed({ place_id: 'a', name: 'A' })
    addToRecentlyViewed({ place_id: 'b', name: 'B' })
    removeFromRecentlyViewed('a')
    expect(getRecentlyViewed().map((x) => x.place_id)).toEqual(['b'])
  })

  it('getRecentlyViewedWithDetails menggabungkan dengan katalog', () => {
    addToRecentlyViewed({ place_id: 'x', name: 'X' })
    const merged = getRecentlyViewedWithDetails([
      { place_id: 'x', name: 'X Full', rating: 4.9 },
      { place_id: 'y', name: 'Y' },
    ])
    expect(merged).toHaveLength(1)
    expect(merged[0].rating).toBe(4.9)
    expect(merged[0].viewedAt).toBeDefined()
  })
})
