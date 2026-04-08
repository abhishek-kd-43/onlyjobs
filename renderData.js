document.addEventListener("DOMContentLoaded", () => {
    fetch('data.json')
      .then(response => response.json())
      .then(data => {
        if (data.status && data.status !== 'success') return;
  
        // -------------------------
        // 1. Homepage Logic (index.html)
        // -------------------------
        const buildPostUrl = (item, category) => {
          const params = new URLSearchParams({ id: item.id });
          if (category) params.set('cat', category);
          return `post.html?${params.toString()}`;
        };

        const renderList = (containerId, items, colorVar, category) => {
          const container = document.getElementById(containerId);
          if (!container) return;
          
          container.innerHTML = '';
          
          if (!items || items.length === 0) {
              container.innerHTML = `<a class="entry" href="#"><div class="entry-text">No updates available.</div></a>`;
              return;
          }

          items.slice(0, 10).forEach((item, idx) => {
            const a = document.createElement('a');
            a.className = 'entry';
            a.href = buildPostUrl(item, category);
            
            let html = `<span class="entry-dot" style="background:var(${colorVar});"></span>`;
            html += `<div><div class="entry-text">${item.title}</div>`;
            
            if (idx < 3) {
               html += `<span class="tag-new" style="margin-left: 5px; font-size:10px; padding: 2px 4px; background:var(${colorVar}); color:#fff; border-radius:4px;">NEW</span>`;
            }
            html += `</div>`;
            a.innerHTML = html;
            
            container.appendChild(a);
          });
        };
  
        // index.html containers
        renderList('live-latest-jobs', data.latest_jobs, '--green', 'latest_jobs');
        renderList('live-admit-cards', data.admit_cards, '--purple', 'admit_cards');
        renderList('live-results', data.results, '--red', 'results');


        // -------------------------
        // 2. Category Pages Logic
        // -------------------------
        
        // Helper to map scraped data (title, source, id) to the rich format
        const buildRichItem = (item, typeParams) => {
            let base = {
                id: item.id,
                t: item.title,
                org: 'Live Update (' + (item.source || 'Scraped') + ')',
                cat: 'Live',
                st: item.state_label || item.state || 'All India',
                ico: typeParams.ico || '🔥',
                bg: '#FEF2F2',
                url: buildPostUrl(item, typeParams.category),
                note: 'Scraped successfully. Click to view local details.'
            };
            return Object.assign(base, typeParams.extra);
        };

        // If on Latest Jobs page
        if (typeof JOBS !== 'undefined' && typeof applyAll === 'function' && data.latest_jobs) {
            const mapped = data.latest_jobs.map(item => buildRichItem(item, {
                ico: '💼',
                category: 'latest_jobs',
                extra: { bdg: 'hot', type: 'Govt Job', qual: '-', age: '-', fee: '-', date: 'Apply Now' }
            }));
            JOBS.unshift(...mapped);
            applyAll();
        }

        // If on Results page
        if (typeof RESULTS !== 'undefined' && typeof applyAll === 'function' && data.results) {
            const mapped = data.results.map(item => buildRichItem(item, {
                ico: '🏆',
                category: 'results',
                extra: { status: 'OUT', badge: 'out', type: 'Result', cutoff: 'Available', date: 'Just Now' }
            }));
            RESULTS.unshift(...mapped);
            applyAll();
        }

        // If on Admit Card page
        if (typeof CARDS !== 'undefined' && typeof applyAll === 'function' && data.admit_cards) {
            const mapped = data.admit_cards.map(item => buildRichItem(item, {
                ico: '🎟️',
                category: 'admit_cards',
                extra: { status: 'OUT', badge: 'out', examDate: 'Live Update', releaseDate: 'Just Now' }
            }));
            CARDS.unshift(...mapped);
            applyAll();
        }

        // If on Answer Key page
        if (typeof AK !== 'undefined' && typeof applyAll === 'function' && data.answer_keys) {
            const mapped = data.answer_keys.map(item => buildRichItem(item, {
                ico: '🔑',
                category: 'answer_keys',
                extra: { keytype: 'FINAL', badge: 'new', objDate: 'Closed', objUrl: '' }
            }));
            AK.unshift(...mapped);
            applyAll();
        }

      })
      .catch(error => {
        console.error('Error fetching live data:', error);
      });
  });
