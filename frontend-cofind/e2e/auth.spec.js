import { test, expect } from '@playwright/test'

test.describe('Login & autentikasi', () => {
  test('halaman login menampilkan form', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByTestId('login-form')).toBeVisible()
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
  })

  test('login gagal untuk kredensial yang tidak valid', async ({ page }) => {
    await page.goto('/login')
    await page.getByTestId('login-username').fill(`nouser_${Date.now()}`)
    await page.getByTestId('login-password').fill('WrongPass1234!')
    await page.getByTestId('login-submit').click()
    await expect(page.getByTestId('login-error')).toBeVisible({ timeout: 20_000 })
  })

  test('registrasi akun baru lalu tidak lagi di halaman login', async ({ page }) => {
    const username = `e2e_${Date.now()}`
    await page.goto('/login')
    await page.getByTestId('login-switch-register').click()
    await expect(page.getByRole('heading', { name: /sign up/i })).toBeVisible()

    await page.getByTestId('login-username').fill(username)
    await page.getByTestId('register-fullname').fill('Pengguna E2E')
    await page.getByTestId('login-password').fill('TestPass1234!')
    await page.getByTestId('register-confirm-password').fill('TestPass1234!')
    await page.getByTestId('login-submit').click()

    await expect(page).not.toHaveURL(/\/login$/, { timeout: 30_000 })
  })
})
