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
  const issue=JSON.parse(fs.readFileSync(path.join(process.cwd(),'data.json'),'utf8'));
  const expectedStoryCount=issue.items.length;
  const hay=item=>[item.title,item.title_en,item.summary,item.summary_en,item.why,item.why_en,item.source].join(' ').toLowerCase();
  // Test a search term unique to the current edition rather than hardcode
  // yesterday's news brand (e.g., Canva), which disappears next day.
  const first=issue.items[0];
  const uniqueTerm=(String(first.title_en).match(/[a-z]{5,}/gi)||[])
    .find(w=>issue.items.filter(item=>hay(item).includes(w.toLowerCase())).length===1);
  assert.ok(uniqueTerm, 'Cannot find a unique test query in first story');
  const output = path.join(process.cwd(), 'reader-screenshots');
  fs.mkdirSync(output,{recursive:true});
  let count = 0;
  try {
    for (const locale of ['zh-hant','zh-hans','en']) {
      for (const width of [320,390,768,1280]) {
        const height=width<=390?844:850;
        const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1});
        const page=await context.newPage();
        page.setDefaultTimeout(8000);
        // Route historical index to this candidate build, not the public live
        // site. A PR test must not depend on production deploy/network status.
        const localIndex=path.join(process.cwd(),'archive',
          locale==='zh-hans'?'search-index-zh-hans.json':'search-index.json');
        await page.route('**/archive/search-index*.json', async route=>{
          await route.fulfill({status:200,contentType:'application/json',path:localIndex});
        });
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
        assert.equal(layout.stories,expectedStoryCount,locale+' article count');
        assert.notEqual(layout.nav,'none',locale+' category menu hidden');
        assert.equal(layout.oldnav,'none',locale+' redundant category strip shown');
        assert.ok(layout.search<=width+2&&layout.langNav<=width+2&&layout.menu<=width+2,locale+' controls off screen: '+JSON.stringify(layout));
        if(width===1280)assert.ok(layout.top.x>layout.intro.x+100,locale+' desktop Top 3 not alongside');
        if(width===390) {
          assert.ok(layout.top.top>=layout.intro.bottom-2,locale+' mobile layout overlap');
          assert.ok(layout.firstLead<height,locale+' first lead not visible without scroll');
        }
        const footer=page.locator('main#main article.story').first().locator('.story-foot');
        assert.equal(await footer.locator('a.readsrc').count(),1,locale+' original CTA missing');
        assert.equal(await footer.locator('details.story-actions').count(),1,locale+' share control missing');
        assert.equal(await footer.locator('.evidence-link').count(),0,locale+' evidence is still a footer CTA');
        assert.equal(await page.locator('main#main article.story .story-meta .evidence-link').count()>=1,true,locale+' supporting source missing from source metadata');
        assert.equal(await page.locator('main#main article.story .story-taxonomy').count(),expectedStoryCount,locale+' tags not located near news context');
        const info=await page.evaluate(()=>{
          const last=document.querySelector('main#main section[id^="sec"]:last-of-type');
          const search=document.getElementById('news-explorer');
          const main=document.getElementById('main');
          return {last:main.querySelectorAll('section[id^="sec"]').length,
                  searchChild:[...main.children].indexOf(search),
                  searchTop:search.getBoundingClientRect().top,
                  lastStoryTop:[...main.querySelectorAll('article.story')].at(-1).getBoundingClientRect().bottom};
        });
        assert.ok(info.searchTop>info.lastStoryTop-5,locale+' bottom search not placed after all news');
        let shown='layout-only';
        // The entire search/reader journey is exercised once per language at
        // phone width. All four widths still verify actual layout/overflow,
        // evidence hierarchy, source buttons and screenshot rendering.
        if (width===390) {
          console.log('BEGIN interactive search and reading: '+locale);
        assert.equal(await page.locator('details.story-expanded[open]').count(),0,locale+' Quick default not collapsed');
        await page.locator('#view-deep').click();
        assert.equal(await page.locator('details.story-expanded[open]').count(),expectedStoryCount,locale+' Deep Read did not open every card');
        assert.equal(await page.locator('#view-deep').getAttribute('aria-pressed'),'true');
        await page.locator('#view-quick').click();
        assert.equal(await page.locator('details.story-expanded[open]').count(),0,locale+' Quick Scan did not close');
        await page.locator('details.story-expanded > summary').first().click();
        assert.equal(await page.locator('details.story-expanded[open]').count(),1,locale+' individual Deep Read failed');
        await page.locator('.top-search').click();
        await page.waitForFunction(()=>document.activeElement?.id==='news-query',{timeout:4000});
        await page.locator('#news-query').fill(uniqueTerm);
        await page.waitForTimeout(180);
        shown=await page.locator('#today-result-list a.today-hit:visible').count();
        assert.ok(shown>=1&&shown<expectedStoryCount,locale+' search results did not appear below field: '+shown);
        assert.equal(await page.locator('article.story:visible').count(),expectedStoryCount,locale+' search hid original news');
        const positions=await page.evaluate(()=>{
          const input=document.getElementById('news-query').getBoundingClientRect();
          const result=document.querySelector('#today-result-list .today-hit').getBoundingClientRect();
          return {inputBottom:input.bottom,resultTop:result.top};
        });
        assert.ok(positions.resultTop>positions.inputBottom,locale+' results appear above search');
        await page.locator('#news-reset').click();
        assert.equal(await page.locator('article.story:visible').count(),expectedStoryCount,locale+' reset hid original news');
        assert.equal(await page.locator('#today-result-list .today-hit:visible').count(),0,locale+' reset left stale results');
        await page.locator('#scope-archive').click();
        await page.waitForSelector('#archive-result-list a.history-hit',{state:'visible',timeout:15000});
        assert.ok(await page.locator('#archive-result-list a.history-hit').count()>=1,locale+' archive search unavailable');
        await page.locator('#scope-today').click();
        assert.equal(await page.locator('article.story:visible').count(),expectedStoryCount,locale+' archive switch hid original news');

        }
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
