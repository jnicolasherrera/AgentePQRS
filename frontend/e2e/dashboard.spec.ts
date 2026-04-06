import { test, expect } from "@playwright/test";

test.describe("Dashboard (authenticated)", () => {
  test.beforeEach(async ({ page }) => {
    // Inject a fake auth token directly into localStorage to bypass real login
    await page.goto("/login");
    await page.evaluate(() => {
      const fakeStore = {
        state: {
          token: "fake-token-for-e2e",
          isAuthenticated: true,
          user: {
            id: "test-id",
            email: "test@sistemapqrs.co",
            nombre: "Test Agent",
            rol: "agente",
            tenant_uuid: "00000000-0000-0000-0000-000000000001",
            cliente_nombre: "SistemaPQRS Test",
          },
        },
        version: 0,
      };
      localStorage.setItem("pqrs-v2-auth", JSON.stringify(fakeStore));
    });
    await page.goto("/");
  });

  test("redirects unauthenticated users to login", async ({ page }) => {
    await page.evaluate(() => localStorage.removeItem("pqrs-v2-auth"));
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });

  test("dashboard page loads without crashing", async ({ page }) => {
    await expect(page.locator("main, [role='main'], #__next")).toBeVisible({ timeout: 10000 });
  });

  test("page title is set", async ({ page }) => {
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
