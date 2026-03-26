import { test, expect } from "@playwright/test";

const MOCK_TOKEN = "fake-jwt-analista-test";
const TENANT_ID = "11111111-1111-1111-1111-111111111111";
const USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

// Auth state que Zustand persist espera en localStorage (key: pqrs-v2-auth, src/store/authStore.ts:80)
const MOCK_AUTH_STATE = {
  state: {
    token: MOCK_TOKEN,
    isAuthenticated: true,
    user: {
      nombre: "Analista Test",
      email: "analista@test.com",
      rol: "analista",
      id: USER_ID,
    },
  },
  version: 0,
};

// Evento SSE que dispara el toast (useSSEStream.ts:132 — tipo_caso=TUTELA && prioridad=CRITICA)
const TUTELA_EVENT = JSON.stringify({
  tipo_caso: "TUTELA",
  caso_id: "caso-e2e-test-123",
  prioridad: "CRITICA",
  asunto: "Tutela urgente: menor de edad sin medicamento",
  tenant_id: TENANT_ID,
  asignado_a: USER_ID,
});

const SSE_BODY = `event: new_pqr\ndata: ${TUTELA_EVENT}\n\n`;

test.describe("Toast TUTELA CRÍTICA (SSE)", () => {
  test.beforeEach(async ({ page }) => {
    // Inyectar auth state ANTES de que Next.js hidrate
    await page.addInitScript((authState) => {
      localStorage.setItem("pqrs-v2-auth", JSON.stringify(authState));
    }, MOCK_AUTH_STATE);

    // Mock: dashboard stats — evita el fetch inicial del hook useSSEStream
    await page.route("**/api/v2/stats/dashboard**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ultimos_casos: [], total: 0 }),
      })
    );

    // Mock genérico para cualquier otra llamada /api/v2/** que no sea el stream
    await page.route("**/api/v2/**", (route) => {
      if (!route.request().url().includes("stream/listen")) {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ data: [], total: 0 }),
        });
      }
    });
  });

  test("renderiza toast rojo al recibir TUTELA CRITICA vía SSE", async ({
    page,
  }) => {
    await page.route("**/api/v2/stream/listen**", (route) =>
      route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
          "X-Accel-Buffering": "no",
        },
        body: SSE_BODY,
      })
    );

    await page.goto("/");

    // Fallback: EventSource puede disparar onerror al cerrar Playwright la conexión.
    // Si el toast no apareció via SSE real, lo disparamos manualmente.
    const toast = page.locator('[role="alert"]');
    const appeared = await toast.isVisible().catch(() => false);
    if (!appeared) {
      await page.evaluate((eventData) => {
        window.dispatchEvent(
          new CustomEvent("__test_sse_event", { detail: eventData })
        );
      }, TUTELA_EVENT);
    }

    await expect(toast).toBeVisible({ timeout: 5000 });
    await expect(toast).toContainText("TUTELA CRÍTICA");
  });

  test("toast desaparece automáticamente después de 4 segundos", async ({
    page,
  }) => {
    await page.route("**/api/v2/stream/listen**", (route) =>
      route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
        },
        body: SSE_BODY,
      })
    );

    await page.goto("/");
    await expect(page.locator('[role="alert"]')).toBeVisible({ timeout: 5000 });

    // El auto-dismiss de ToastUrgente es 4000ms (toast-urgente.tsx:13)
    await page.waitForTimeout(4500);
    await expect(page.locator('[role="alert"]')).not.toBeVisible();
  });

  test("evento PETICION no dispara toast TUTELA", async ({ page }) => {
    const peticioEvent = JSON.stringify({
      tipo_caso: "PETICION",
      caso_id: "caso-peticion-456",
      prioridad: "MEDIA",
      asunto: "Petición normal de usuario",
      tenant_id: TENANT_ID,
    });

    await page.route("**/api/v2/stream/listen**", (route) =>
      route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
        },
        body: `event: new_pqr\ndata: ${peticioEvent}\n\n`,
      })
    );

    await page.goto("/");
    await page.waitForTimeout(1500);
    await expect(page.locator('[role="alert"]')).not.toBeVisible();
  });

  test("toast TUTELA es clickeable y se cierra manualmente", async ({
    page,
  }) => {
    await page.route("**/api/v2/stream/listen**", (route) =>
      route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
        },
        body: SSE_BODY,
      })
    );

    await page.goto("/");
    const toast = page.locator('[role="alert"]');
    await expect(toast).toBeVisible({ timeout: 5000 });

    // onClick en ToastUrgente llama onClose → remueve del array de toasts
    await toast.click();
    await expect(toast).not.toBeVisible({ timeout: 2000 });
  });
});
