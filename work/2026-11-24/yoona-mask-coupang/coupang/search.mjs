import { chromium } from 'playwright';
import { writeFile } from 'node:fs/promises';
const out = new URL('.', import.meta.url).pathname;
const q = process.argv[2] ?? '설화수 자음생 마스크';
const ctx = await chromium.launchPersistentContext(out + '.profile', { channel: 'chrome', headless: false, viewport: { width: 1280, height: 2000 }, locale: 'ko-KR', args: ['--disable-blink-features=AutomationControlled'] });
const browser = ctx;
const page = await ctx.newPage();
await page.goto(`https://www.coupang.com/np/search?q=${encodeURIComponent(q)}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(4000);
await page.screenshot({ path: out + 'search.png', fullPage: false });
const items = await page.evaluate(() => Array.from(document.querySelectorAll('li[class*="ProductUnit"], li.search-product, ul#product-list > li')).slice(0, 12).map(li => ({
  name: li.querySelector('[class*="productName"], .name')?.textContent?.trim(),
  price: li.querySelector('[class*="priceValue"], .price-value, strong')?.textContent?.trim(),
  rating: li.querySelector('[class*="rating"], .rating')?.textContent?.trim(),
  reviews: li.querySelector('[class*="ratingCount"], .rating-total-count')?.textContent?.trim(),
  href: li.querySelector('a')?.href,
})));
console.log(await page.title());
console.log(JSON.stringify(items, null, 1));
await writeFile(out + 'search.json', JSON.stringify(items, null, 1));
await browser.close();
