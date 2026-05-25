import { test, expect } from '@playwright/test'

/**
 * CoFind bukan toko checkout: tidak ada alur keranjang/pembayaran.
 * Di sini "alur pengguna" = akses area terlindungi + pengiriman form profil.
 */
test.describe('Alur pengguna (bukan checkout e-commerce)', () => {
  test('guest yang membuka /profile diarahkan ke login', async ({ page }) => {
    await page.goto('/profile')
    await expect(page).toHaveURL(/\/login/)
  })

  test('setelah daftar, halaman profil tampil dan form nickname bisa disimpan', async ({
    page,
  }) => {
    const username = `e2e_prof_${Date.now()}`
    const nickname = `Nick ${Date.now()}`

    await page.goto('/login')
    await page.getByTestId('login-switch-register').click()
    await page.getByTestId('login-username').fill(username)
    await page.getByTestId('login-password').fill('TestPass1234!')
    await page.getByTestId('register-confirm-password').fill('TestPass1234!')
    await page.getByTestId('login-submit').click()

    await expect(page).not.toHaveURL(/\/login$/, { timeout: 30_000 })

    await page.goto('/profile')
    await expect(page.getByTestId('profile-page')).toBeVisible({ timeout: 20_000 })
    await expect(page.getByTestId('profile-display-name')).toBeVisible()

    await page.getByTestId('profile-open-edit').click()
    await expect(page.getByTestId('profile-edit-form')).toBeVisible()
    await page.getByTestId('profile-edit-nickname').fill(nickname)
    await page.getByTestId('profile-save').click()

    await expect(page.getByTestId('profile-display-name')).toContainText(nickname, {
      timeout: 15_000,
    })
  })
})
