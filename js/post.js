/* post.js: reading aids for blog posts (redesign, October 2026).

   Added to every post by scripts/post_polish.py. Two things, both quiet:

   1. A thin reading-progress bar along the top of the window.
   2. A "Contents" list for long posts (four or more section headings),
      placed just above the article body. Headings without an id get one
      from their text, so the links also work as shareable #anchors.

   Styles live in css/site-footer.css under "POSTS". Nothing here is needed
   to read the post; if the script fails, the page is unchanged. */
(function () {
  var body = document.querySelector('.article-body');
  if (!body) return;

  // 1. progress bar
  var bar = document.createElement('div');
  bar.className = 'post-progress';
  bar.setAttribute('aria-hidden', 'true');
  document.body.appendChild(bar);
  var ticking = false;
  function update() {
    var r = body.getBoundingClientRect();
    var total = r.height - window.innerHeight * 0.6;
    var done = Math.min(1, Math.max(0, -r.top / (total > 0 ? total : 1)));
    bar.style.transform = 'scaleX(' + done + ')';
    ticking = false;
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }, { passive: true });
  window.addEventListener('resize', update);
  update();

  // 2. contents
  var heads = Array.prototype.filter.call(body.querySelectorAll('h2'), function (h) {
    return h.textContent.trim().length > 0 && !h.closest('.keep-reading');
  });
  if (heads.length < 4 || document.querySelector('.post-toc')) return;
  var used = {};
  function slug(t) {
    var s = t.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'section';
    var k = s, n = 2;
    while (used[k] || (document.getElementById(k) && !used[k])) { k = s + '-' + n++; }
    used[k] = 1;
    return k;
  }
  var nav = document.createElement('details');
  nav.className = 'post-toc';
  if (window.matchMedia && matchMedia('(min-width: 900px)').matches) nav.open = true;
  var sum = document.createElement('summary');
  sum.textContent = 'Contents';
  nav.appendChild(sum);
  var ol = document.createElement('ol');
  heads.forEach(function (h) {
    if (!h.id) h.id = slug(h.textContent);
    var li = document.createElement('li');
    var a = document.createElement('a');
    a.href = '#' + h.id;
    a.textContent = h.textContent.replace(/\s+/g, ' ').trim();
    li.appendChild(a);
    ol.appendChild(li);
  });
  nav.appendChild(ol);
  body.parentNode.insertBefore(nav, body);
})();
