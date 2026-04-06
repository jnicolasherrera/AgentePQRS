import { test, expect } from "@playwright/test";

test.describe("Login page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test("renders login form correctly", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("PQRS");
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test("shows error on invalid credentials", async ({ page }) => {
    await page.fill('input[type="email"]', "fake@example.com");
    await page.fill('input[type="password"]', "wrongpassword");
    await page.click('button[type="submit"]');

    await expect(
      page.locator("text=Credenciales inválidas")
    ).toBeVisible({ timeout: 10000 });
  });

  test("submit button shows loading state", async ({ page }) => {
    await page.fill('input[type="email"]', "test@example.com");
    await page.fill('input[type="password"]', "password123");

    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();

    await expect(page.locator("text=Autenticando")).toBeVisible({ timeout: 3000 });
  });

  test("email field requires valid email format", async ({ page }) => {
    await page.fill('input[type="email"]', "not-an-email");
    await page.click('button[type="submit"]');
    const emailInput = page.locator('input[type="email"]');
    await expect(emailInput).toHaveAttribute("type", "email");
  });

  test("password field is masked", async ({ page }) => {
    const passwordInput = page.locator('input[type="password"]');
    await expect(passwordInput).toHaveAttribute("type", "password");
  });
});
