/*
 * Минимальная офлайн-реализация HTMX-атрибутов для локального viewer.
 * Поддерживает hx-get / hx-post + hx-target + hx-trigger (debounce, load).
 * Делегирование на document — новые фрагменты работают без перепривязки.
 * В S05+ планируется замена на полный локальный vendor-HTMX.
 */
(function () {
  function collect(form) {
    var data = new URLSearchParams();
    form.querySelectorAll('input, select').forEach(function (el) {
      if (el.name) data.set(el.name, el.value);
    });
    return data.toString();
  }

  async function load(el) {
    var target = document.querySelector(el.getAttribute('hx-target') || '');
    if (!target) return;
    var isPost = el.hasAttribute('hx-post');
    var rawUrl = el.getAttribute(isPost ? 'hx-post' : 'hx-get');
    if (!rawUrl) return;
    var url = rawUrl;
    var options = { headers: { 'X-Requested-With': 'htmx-lite' } };
    if (el.tagName === 'FORM') {
      var query = collect(el);
      if (query) url += (url.indexOf('?') === -1 ? '?' : '&') + query;
    }
    if (isPost) {
      options.method = 'POST';
    }
    try {
      var response = await fetch(url, options);
      if (response.ok) {
        target.innerHTML = await response.text();
      } else {
        target.innerHTML = '<p class="muted">Ошибка запроса: ' + response.status + '</p>';
      }
    } catch (e) {
      target.innerHTML = '<p class="muted">Не удалось загрузить данные: ' + e.message + '</p>';
    }
  }

  document.addEventListener('click', function (e) {
    var el = e.target.closest('[hx-get], [hx-post]');
    if (!el || el.tagName === 'FORM') return;
    e.preventDefault();
    load(el);
  });

  document.addEventListener('input', function (e) {
    var form = e.target.closest('form[hx-get]');
    if (!form) return;
    clearTimeout(form._hxTimer);
    form._hxTimer = setTimeout(function () { load(form); }, 250);
  });

  document.addEventListener('change', function (e) {
    var form = e.target.closest('form[hx-get]');
    if (form) load(form);
  });

  document.addEventListener('submit', function (e) {
    var form = e.target.closest('form[hx-get], form[hx-post]');
    if (!form) return;
    e.preventDefault();
    load(form);
  });

  document.querySelectorAll('[hx-trigger~="load"]').forEach(function (el) {
    load(el);
  });
})();
