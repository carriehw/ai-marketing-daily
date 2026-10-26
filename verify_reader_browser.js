/* Headless Chromium smoke coverage for trilingual Reader-first pages.
   Tests real layout width, keyboard/selector usability and reading actions.
   The public website is NOT modified by this script. */
const {chromium} = require('playwright');
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');

(async function main() {
  const base = process.env.READER_TEST_URL || 'http://127.0.0.1:8765/ai-marketing-daily/';
  const browser = await chromium.launch({headless: true, args:['--no-sandbox']});
  const output = path.join(process.cwd(), 'reader-screenshots');
  fs.mkdirSync(output,{recursive:true});
  let count = 0;
  try {
    for (const locale of ['zh-hant','zh-hans','en']) {
      for (const width of [390,768,1280]) {
        const height=width===390?844:850;
        const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1});
        const page=await context.newPage();
        const errors=[];
        page.on('pageerror',e=>errors.push(e.message));
        await page.goto(base+locale+'/',{waitUntil:'domcontentloaded',timeout:30000});
        await page.waitForSelector('#view-deep',{state:'attached'});
        const layout=await page.evaluate(()=>{
          const box=s=>document.querySelector(s)?.getBoundingClientRect();
          const home=document.querySelector('.top-stories');
          const leads=[...document.querySelectorAll('.top-stories .lead-row')];
          const bar=box('.topbar'),feature=box('.hero-feature-grid'),intro=box('.hero-intro'),top=box('.top-stories');
          return {
            lang:document.documentElement.lang,
            scrollWidth:document.documentElement.scrollWidth,
            viewport:window.innerWidth,
            top3:leads.length,
            stories:document.querySelectorAll('article.story').length,
            firstLead:leads[0]?.getBoundingClientRect().top,
            feature:{x:feature?.x,width:feature?.width},
            intro:{x:intro?.x,top:intro?.top,right:intro?.right,bottom:intro?.bottom},
            top:{x:top?.x,top:top?.top,right:top?.right,bottom:top?.bottom},
            nav:getComputedStyle(document.querySelector('.mobile-category-menu')).display,
            oldnav:getComputedStyle(document.querySelector('.navlinks')).display,
            bar:{x:bar?.x,right:bar?.right},
            search:box('.top-search')?.right,
            langNav:box('.locale-links')?.right,
            menu:box('#mobile-categories')?.right
          };
        });
        assert.equal(layout.lang,locale==='en'?'en':locale==='zh-hans'?'zh-Hans':'zh-Hant', locale+' language');
        assert.ok(layout.scrollWidth<=width+2,locale+' '+width+' horizontal overflow: '+JSON.stringify(layout));
        assert.equal(layout.top3,3,locale+' top three');
        assert.equal(layout.stories,14,locale+' article count');
        assert.notEqual(layout.nav,'none',locale+' category menu hidden');
        assert.equal(layout.oldnav,'none',locale+' redundant category strip shown');
        assert.ok(layout.search<=width+2&&layout.langNav<=width+2&&layout.menu<=width+2,locale+' controls off screen: '+JSON.stringify(layout));
        if(width===1280)assert.ok(layout.top.x>layout.intro.x+100,locale+' desktop Top 3 not alongside');
        if(width===390) {
          assert.ok(layout.top.top>=layout.intro.bottom-2,locale+' mobile layout overlap');
          assert.ok(layout.firstLead<height,locale+' first lead not visible without scroll');
        }
        assert.equal(await page.locator('details.story-expanded[open]').count(),0,locale+' Quick default not collapsed');
        await page.locator('#view-deep').click();
        assert.equal(await page.locator('details.story-expanded[open]').count(),14,locale+' Deep Read did not open every card');
        assert.equal(await page.locator('#view-deep').getAttribute('aria-pressed'),'true');
        await page.locator('#view-quick').click();
        assert.equal(await page.locator('details.story-expanded[open]').count(),0,locale+' Quick Scan did not close');
        await page.locator('details.story-expanded > summary').first().click();
        assert.equal(await page.locator('details.story-expanded[open]').count(),1,locale+' individual Deep Read failed');
        await page.locator('.top-search').click();
        await page.waitForFunction(()=>document.activeElement?.id==='news-query',{timeout:4000});
        await page.locator('#news-query').fill('Canva');
        await page.waitForTimeout(180);
        const shown=await page.locator('article.story:visible').count();
        assert.ok(shown>=1&&shown<14,locale+' search filtering did not work: '+shown);
        await page.locator('#news-reset').click();
        assert.equal(await page.locator('article.story:visible').count(),14,locale+' reset failed');
        await page.screenshot({path:path.join(output,locale+'-'+width+'.png'),fullPage:false});
        assert.deepEqual(errors,[],locale+' JavaScript page errors');
        console.log('PASS '+locale+' '+width+'px',JSON.stringify({scrollWidth:layout.scrollWidth,firstLead:Math.round(layout.firstLead),visibleAfterSearch:shown}));
        count++;
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
  console.log('PASS Reader-first Chromium visual and interactive smoke: '+count+' locale/viewport cases');
})().catch(err=>{console.error('FAIL Reader-first browser QA:',err);process.exitCode=1;});
