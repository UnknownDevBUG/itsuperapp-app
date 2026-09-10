import { test, expect } from "@playwright/test";

test("browser can reach the site's login page", async ({ page }) => {
	await page.goto("/login");
	await expect(page.locator("#login_email, input[data-fieldname='usr']")).toBeVisible({
		timeout: 10_000,
	});
});
