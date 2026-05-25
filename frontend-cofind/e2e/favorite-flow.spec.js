import { test, expect } from '@playwright/test'

const API_BASE =
  process.env.PLAYWRIGHT_API_BASE ||
  `http://127.0.0.1:${process.env.PW_E2E_API_PORT || '5055'}`

/**
 * CoFind tidak punya checkout/pembayaran. Alur "transaksi" dari sudut pengguna
 * yang paling dekat: komitmen ke daftar (tambah favorit) setelah login.
 */
test.describe('Alur komitmen pengguna (favorit)', () => {
  test('user login dapat menambah toko ke favorit dari halaman detail', async ({
    page,
    request,
  }) => {
    const listRes = await request.get(`${API_BASE}/api/coffeeshops`)
    expect(listRes.ok()).toBeTruthy()
    const listJson = await listRes.json()
    const shops = Array.isArray(listJson.data) ? listJson.data : []
    test.skip(
      shops.length === 0,
      'Butuh minimal satu baris coffee_shops di backend (data lokal).',
    )

    const placeId = String(shops[0].place_id || '').trim()
    expect(placeId.length).toBeGreaterThan(0)

    const username = `e2e_fav_${Date.now()}`
    await page.goto('/login')
    await page.getByTestId('login-switch-register').click()
    await page.getByTestId('login-username').fill(username)
    await page.getByTestId('login-password').fill('TestPass1234!')
    await page.getByTestId('register-confirm-password').fill('TestPass1234!')
    await page.getByTestId('login-submit').click()
    await expect(page).not.toHaveURL(/\/login$/, { timeout: 30_000 })

    await page.goto(`/shop/${encodeURIComponent(placeId)}`)
    await expect(page.getByTestId('shop-toggle-favorite')).toBeVisible({ timeout: 30_000 })

    await page.getByTestId('shop-toggle-favorite').click()
    await expect(page.getByTestId('shop-notification')).toContainText(/favorit/i, {
      timeout: 15_000,
    })
  })
})
