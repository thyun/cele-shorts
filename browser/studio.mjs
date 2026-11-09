import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { chmod, mkdir } from 'node:fs/promises';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const profilePath = path.join(root, '.browser-profile');
const studioUrl = 'https://studio.youtube.com/';
const args = process.argv.slice(2);

if (args.length > 1 || (args.length === 1 && args[0] !== '--check')) {
  console.error('사용법: npm run browser:open 또는 npm run browser:check');
  process.exitCode = 1;
} else if (args[0] === '--check') {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage();
    await page.setContent('<title>Browser check</title><h1>Browser ready</h1>');
    if (await page.locator('h1').textContent() !== 'Browser ready') {
      throw new Error('브라우저 페이지 검증 실패');
    }
    console.log('Chrome 자동화 연결 확인 완료');
  } finally {
    await browser.close();
  }
} else {
  await mkdir(profilePath, { recursive: true, mode: 0o700 });
  await chmod(profilePath, 0o700);
  const context = await chromium.launchPersistentContext(profilePath, {
    channel: 'chrome',
    headless: false,
  });
  try {
    const page = context.pages()[0] ?? await context.newPage();
    await page.goto(studioUrl, { waitUntil: 'domcontentloaded' });
    console.log('Chrome에서 직접 로그인하세요. 종료하려면 브라우저 창을 닫으세요.');
    await new Promise((resolve) => context.once('close', resolve));
  } catch (error) {
    await context.close();
    throw error;
  }
}
