import assert from 'node:assert/strict';
import fs from 'node:fs';

const app = fs.readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const analytics = fs.readFileSync(new URL('../analytics.js', import.meta.url), 'utf8');
const page = fs.readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const posting = fs.readFileSync(new URL('../content/posting-pack-01.md', import.meta.url), 'utf8');

assert.match(app, /rawSrc = params\.get\('src'\)/);
assert.match(app, /explicitContentId = params\.get\('content_id'\)/);
assert.match(app, /\/\^short\\d\+\$\//);
assert.match(app, /content_id: explicitContentId \|\| legacyContentMatch \|\| 'unknown'/);
assert.match(app, /emit\('binance_referral_click'/);
assert.match(app, /dataLayer\.push\(payload\)/);
assert.match(app, /window\.dispatchEvent\(new CustomEvent\('rpg:event'/);
assert.equal((app.match(/getElementById\('binanceCta'\)\.addEventListener\('click'/g) || []).length, 1);
assert.match(analytics, /window\.gtag\('event', eventName, params\)/);
assert.equal((page.match(/id="binanceCta"/g) || []).length, 1);

for (const contentId of Array.from({ length: 10 }, (_, index) => `short${String(index + 1).padStart(2, '0')}`)) {
  const expected = `?src=yt_${contentId}&content_id=${contentId}`;
  assert.match(posting, new RegExp(expected.replace(/[?&=]/g, '\\$&')));
}

console.log('GA4 attribution compatibility contract passed');
