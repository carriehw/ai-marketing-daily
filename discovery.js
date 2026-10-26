/* AI Marketing Daily — reader discovery and team brief, version 2.
   Runs on the homepage and new archive snapshots. Zero frameworks/back-end.
   Search index is fetched lazily only when historical search is requested. */
(function () {
  'use strict';
  const config = document.getElementById('news-discovery-data');
  const panel = document.getElementById('news-explorer');
  if (!config || !panel) return;
  let edition;
  try { edition = JSON.parse(config.textContent); }
  catch (err) { console.warn('News discovery data unavailable', err); return; }

  const siteBase = new URL(edition.site_base, location.origin);
  const editionBase = new URL(edition.edition_base || edition.site_base, location.origin);
  const byId = new Map(edition.items.map(item => [item.id, item]));
  const input = document.getElementById('news-query');
  const category = document.getElementById('news-section');
  const signal = document.getElementById('news-signal');
  const scopeToday = document.getElementById('scope-today');
  const scopeArchive = document.getElementById('scope-archive');
  const reset = document.getElementById('news-reset');
  const status = document.getElementById('news-status');
  const archiveBox = document.getElementById('archive-search-results');
  const archiveList = document.getElementById('archive-result-list');
  const todayBox = document.getElementById('today-search-results');
  const todayList = document.getElementById('today-result-list');
  const more = document.getElementById('archive-more');
  const empty = document.getElementById('news-empty');
  const manualBox = document.getElementById('brief-manual');
  const manualInput = document.getElementById('brief-manual-text');
  const manualClose = document.getElementById('brief-manual-close');
  if (!input || !category || !signal || !scopeToday || !scopeArchive ||
      !reset || !status || !archiveBox || !archiveList || !todayBox ||
      !todayList || !more || !empty) return;

  let mode = 'today';
  let historical = null, archiveError = false, visibleLimit = 24, request = null;
  const lang = () => document.documentElement.getAttribute('data-lang') === 'en' ? 'en' : 'zh';
  const tr = (zh, en) => lang() === 'en' ? en : zh;
  const normal = s => String(s || '').normalize('NFKC').toLocaleLowerCase().trim();
  const qs = (key) => normal(key).split(/\s+/).filter(Boolean);
  const hasAll = (hay, terms) => terms.every(term => hay.includes(term));
  const cards = Array.from(document.querySelectorAll('main#main article.story'));
  const archiveUrl = (path) => {
    const url = new URL('archive/' + path, editionBase);
    url.searchParams.set('lang', lang());
    return url.href;
  };
  const stableStoryUrl = (id) => archiveUrl(edition.date + '.html' + (id ? '#' + id : ''));
  const setStatus = message => { status.textContent = message; };
  function refreshLocaleControls() {
    for (const sel of [category, signal]) {
      for (const opt of sel.options) {
        opt.textContent = lang() === 'en' ? opt.dataset.en : opt.dataset.zh;
      }
    }
    input.placeholder = lang() === 'en' ? input.dataset.placeholderEn : input.dataset.placeholderZh;
  }
  const filtersActive = () => input.value.trim() || category.value !== 'all' || signal.value !== 'all';
  const scopeChange = where => {
    mode = where;
    scopeToday.setAttribute('aria-pressed', where === 'today' ? 'true' : 'false');
    scopeArchive.setAttribute('aria-pressed', where === 'archive' ? 'true' : 'false');
    panel.classList.toggle('is-history', where === 'archive');
    archiveBox.hidden = where !== 'archive';
    todayBox.hidden = where !== 'today' || !filtersActive();
    empty.hidden = true;
    if (where === 'archive') ensureHistory();
    else render();
  };
  function renderToday() {
    const terms = qs(input.value);
    const sec = category.value, sig = signal.value;
    const active = !!filtersActive();
    todayList.replaceChildren();
    todayBox.hidden = !active;
    archiveBox.hidden = true;
    empty.hidden = true;
    if (!active) {
      setStatus(tr('今日共有 ' + edition.items.length + ' 則新聞。輸入關鍵字或選擇分類開始搜尋。',
                   edition.items.length + ' stories today. Enter a keyword or choose a filter.'));
      return;
    }
    const results = edition.items.filter(item => {
      const combined = normal([
        item.title, item.title_en, item.summary, item.summary_en,
        item.why, item.why_en, item.source
      ].join(' '));
      return (sec === 'all' || String(item.section) === sec)
        && (sig === 'all' || item.signal === sig)
        && hasAll(combined, terms);
    });
    for (const item of results) {
      const target = document.getElementById(item.id);
      if (!target) continue;
      const link = document.createElement('a');
      link.className = 'history-hit today-hit';
      link.href = '#' + encodeURIComponent(item.id);
      const title = document.createElement('strong');
      title.textContent = lang() === 'en' ? item.title_en : item.title;
      const meta = document.createElement('small');
      meta.textContent = item.source + ' · ' +
        tr('點擊前往完整新聞', 'Jump to full story');
      const excerpt = document.createElement('span');
      excerpt.textContent = lang() === 'en' ? item.summary_en : item.summary;
      link.append(title, meta, excerpt);
      todayList.appendChild(link);
    }
    empty.hidden = results.length !== 0;
    setStatus(tr('找到 ' + results.length + ' 則今日新聞（共 ' + edition.items.length + ' 則），結果顯示如下。',
                 results.length + ' of ' + edition.items.length + ' stories. Results appear below.'));
  }
  function archiveRows() {
    if (!historical) return [];
    const terms = qs(input.value);
    const sec = category.value, sig = signal.value;
    return historical.items.filter(item => {
      if (sec !== 'all' && String(item.section) !== sec) return false;
      if (sig !== 'all' && item.signal !== sig) return false;
      return hasAll(normal([item.title_zh, item.title_en,
        item.summary_zh, item.summary_en, item.source, item.date].join(' ')), terms);
    });
  }
  function clearList() { archiveList.replaceChildren(); }
  function addResult(item) {
    const link = document.createElement('a');
    link.className = 'history-hit';
    // Only internal dated archive links in the generated JSON are accepted.
    if (!/^\d{4}-\d{2}-\d{2}\.html(?:#[A-Za-z0-9_-]+)?$/.test(item.url)) return;
    link.href = archiveUrl(item.url);
    const title = document.createElement('strong');
    title.textContent = (lang() === 'en' ? item.title_en : item.title_zh) ||
                        item.title_zh || item.title_en;
    const meta = document.createElement('small');
    meta.textContent = item.date + (item.source ? ' · ' + item.source : '');
    const excerpt = document.createElement('span');
    excerpt.textContent = (lang() === 'en' ? item.summary_en : item.summary_zh) || '';
    link.append(title, meta, excerpt);
    archiveList.appendChild(link);
  }
  function renderHistory() {
    if (archiveError) {
      clearList();
      more.hidden = true;
      empty.hidden = false;
      setStatus(tr('歷史搜尋資料暫時未能載入，今日新聞仍可正常查看。',
                   'Archive search is temporarily unavailable; today’s news still works.'));
      return;
    }
    if (!historical) {
      setStatus(tr('正在載入歷史新聞目錄…', 'Loading archive search index…'));
      return;
    }
    const results = archiveRows();
    clearList();
    results.slice(0, visibleLimit).forEach(addResult);
    empty.hidden = results.length !== 0;
    more.hidden = results.length <= visibleLimit;
    more.textContent = tr('顯示更多結果', 'Show more results');
    setStatus(tr(`搜尋 ${historical.issue_count} 期存檔：找到 ${results.length} 則，顯示 ${Math.min(results.length,visibleLimit)} 則`,
                 `${results.length} matches across ${historical.issue_count} issues; showing ${Math.min(results.length,visibleLimit)}`));
  }
  function ensureHistory() {
    if (historical || archiveError) return renderHistory();
    if (!request) {
      setStatus(tr('正在載入歷史新聞目錄…', 'Loading archive search index…'));
      const searchPath = document.documentElement.lang === 'zh-Hans'
        ? 'archive/search-index-zh-hans.json' : 'archive/search-index.json';
      request = fetch(new URL(searchPath, siteBase), {credentials:'omit'})
        .then(response => {
          if (!response.ok) throw new Error('Archive index HTTP ' + response.status);
          return response.json();
        })
        .then(index => {
          if (!index || index.version !== 1 || !Array.isArray(index.items) ||
              index.count !== index.items.length) throw new Error('Invalid archive search index');
          historical = index;
        })
        .catch(err => { archiveError = true; console.warn('History search error', err); })
        .finally(() => { if (mode === 'archive') renderHistory(); });
    }
  }
  function render() {
    if (mode === 'today') return renderToday();
    ensureHistory();
    if (historical || archiveError) renderHistory();
  }
  let debounce;
  input.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => { visibleLimit = 24; render(); }, 120);
  });
  category.addEventListener('change', () => {visibleLimit = 24; render();});
  signal.addEventListener('change', () => {visibleLimit = 24; render();});
  scopeToday.addEventListener('click', () => scopeChange('today'));
  scopeArchive.addEventListener('click', () => scopeChange('archive'));
  reset.addEventListener('click', () => {
    input.value = ''; category.value = 'all'; signal.value = 'all';
    visibleLimit = 24; mode === 'archive' ? scopeChange('today') : render();
    input.focus();
  });
  more.addEventListener('click', () => { visibleLimit += 24; renderHistory(); });
  const watchLang = new MutationObserver(() => {
    refreshLocaleControls();
    render();
  });
  watchLang.observe(document.documentElement, {attributes: true, attributeFilter:['data-lang']});
  refreshLocaleControls();
  render();

  const formatTeamBrief = item => {
    const isEn = lang() === 'en';
    const name = isEn ? (item.title_en || item.title) : item.title;
    const summary = isEn ? (item.summary_en || item.summary) : item.summary;
    const why = isEn ? (item.why_en || item.why) : item.why;
    const next = isEn ? item.next_step_en : item.next_step;
    const source = item.source || '';
    const url = stableStoryUrl(item.id);
    return [
      `AI Marketing Daily | ${edition.date}`,
      '',
      name,
      '',
      (isEn ? 'What happened: ' : '發生什麼：') + summary,
      (isEn ? 'Why marketers care: ' : '對行銷團隊的影響：') + why,
      next ? (isEn ? 'Recommended next step: ' : '建議下一步：') + next : '',
      '',
      (isEn ? 'Source: ' : '資料來源：') + source + ' | ' + item.time,
      item.url,
      '',
      (isEn ? 'Read this brief: ' : '閱讀本站整理：') + url,
    ].filter((part, i, arr) => part !== '' || (i && arr[i-1] !== '')).join('\n').trim();
  };
  async function writeClipboard(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (e) { /* Try old browser fallback. */ }
    const dummy = document.createElement('textarea');
    dummy.value = text;
    dummy.setAttribute('readonly', '');
    dummy.style.cssText = 'position:fixed;top:-10000px;left:-10000px;opacity:0';
    document.body.appendChild(dummy);
    dummy.select();
    let success = false;
    try { success = document.execCommand('copy'); } catch (e) {}
    dummy.remove();
    return success;
  }
  document.querySelectorAll('.story-actions').forEach(menu => {
    const button = menu.querySelector('[data-action="copy"]');
    if (!button) return;
    button.addEventListener('click', async () => {
      menu.open = false;
      const item = byId.get(menu.dataset.story);
      if (!item) return;
      const contents = formatTeamBrief(item);
      const ok = await writeClipboard(contents);
      if (ok) {
        const toast = document.getElementById('toast');
        if (typeof window.toast === 'function') {
          window.toast(tr('Team Brief 已複製，可分享給同事',
                          'Team brief copied — ready to share'));
        } else if (toast) {
          toast.textContent = tr('Team Brief 已複製', 'Team brief copied');
          toast.classList.add('on');
          setTimeout(() => toast.classList.remove('on'), 2200);
        }
      } else if (manualBox && manualInput) {
        manualInput.value = contents;
        manualBox.hidden = false;
        manualInput.focus();
        manualInput.select();
      }
    });
  });
  if (manualClose && manualBox) manualClose.addEventListener('click',
    () => { manualBox.hidden = true; });
})();
