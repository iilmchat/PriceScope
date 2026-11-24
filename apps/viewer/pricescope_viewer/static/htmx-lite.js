/*
 * Минимальная офлайн-реализация HTMX-атрибутов для локального viewer (S05).
 * Поддерживает hx-get + hx-target + hx-trigger="input changed delay:250ms, load".
 * В S05 планируется замена на полный HTMX из static/vendor/.
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
    var url = el.getAttribute('hx-get');
    var target = document.querySelector(el.getAttribute('hx-target'));
    if (!url || !target) return;
    var query = el.tagName === 'FORM' ? collect(el) : '';
    try {
      var response = await fetch(url + (query ? '?' + query : ''), {
        headers: { 'X-Requested-With': 'htmx-lite' },
      });
      if (response.ok) target.innerHTML = await response.text();
    } catch (e) {
      target.innerHTML = '<p class="muted">Не удалось загрузить данные: ' + e.message + '</p>';
    }
  }
  document.querySelectorAll('[hx-get]').forEach(function (el) {
    var trigger = el.getAttribute('hx-trigger') || '';
    if (trigger.indexOf('load') !== -1) load(el);
    if (el.tagName === 'FORM') {
      var timer;
      el.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(function () { load(el); }, 250);
      });
      el.addEventListener('change', function () { load(el); });
      el.addEventListener('submit', function (e) { e.preventDefault(); load(el); });
    }
  });
})();
