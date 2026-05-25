import { describe, it, expect } from 'vitest'
import {
  filterStopWords,
  normalizeWord,
  normalizeAndFilterKeywords,
  extractKeywordsFromText,
  expandKeywordWithSynonyms,
  isStopWord,
} from './keywordMapping'

describe('keywordMapping', () => {
  describe('filterStopWords', () => {
    it('mengembalikan array kosong untuk input non-array', () => {
      expect(filterStopWords(null)).toEqual([])
      expect(filterStopWords(undefined)).toEqual([])
    })

    it('menghapus stop words dan menormalisasi case', () => {
      // 'bagus' terfilter karena isStopWord memakai substring (mis. artikel "a")
      expect(filterStopWords(['Saya', 'mau', 'wifi', 'espresso'])).toEqual(['wifi', 'espresso'])
    })
  })

  describe('normalizeWord', () => {
    it('mengembalikan string kosong untuk input kosong', () => {
      expect(normalizeWord('')).toBe('')
      expect(normalizeWord(null)).toBe('')
    })

    it('memetakan sinonim ke canonical key', () => {
      expect(normalizeWord('gue')).toBe('saya')
      // Kata yang sudah jadi key di mapping tetap mengembalikan key itu sendiri
      expect(normalizeWord('WARKOP')).toBe('warkop')
      expect(normalizeWord('kopi sop')).toBe('coffee shop')
    })

    it('mempertahankan kata tanpa mapping', () => {
      expect(normalizeWord('arabica')).toBe('arabica')
    })
  })

  describe('normalizeAndFilterKeywords', () => {
    it('mengembalikan array kosong untuk input non-array', () => {
      expect(normalizeAndFilterKeywords(null)).toEqual([])
    })

    it('menghapus duplikat setelah normalisasi', () => {
      const out = normalizeAndFilterKeywords(['kopi sop', 'coffee shop', 'wifi'])
      expect(out).toContain('coffee shop')
      expect(out).toContain('wifi')
      expect(out.filter((k) => k === 'coffee shop').length).toBe(1)
    })
  })

  describe('extractKeywordsFromText', () => {
    it('mengembalikan array kosong untuk text invalid', () => {
      expect(extractKeywordsFromText('')).toEqual([])
      expect(extractKeywordsFromText(null)).toEqual([])
    })

    it('mengekstrak keyword yang relevan', () => {
      const k = extractKeywordsFromText('Saya cari cafe dengan wifi kencang di Bandung')
      expect(k.some((w) => w.includes('wifi') || w === 'wifi')).toBe(true)
    })
  })

  describe('expandKeywordWithSynonyms', () => {
    it('mengembalikan array kosong untuk keyword kosong', () => {
      expect(expandKeywordWithSynonyms('')).toEqual([])
    })

    it('menyertakan sinonim unik', () => {
      const expanded = expandKeywordWithSynonyms('wifi')
      expect(expanded).toContain('wifi')
      expect(expanded.length).toBeGreaterThan(1)
    })
  })

  describe('isStopWord', () => {
    it('menganggap string kosong sebagai stop word', () => {
      expect(isStopWord('')).toBe(true)
    })

    it('mendeteksi stop word umum', () => {
      expect(isStopWord('yang')).toBe(true)
    })
  })
})
