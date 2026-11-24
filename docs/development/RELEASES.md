# Процесс релизов PriceScope

**Назначение:** единый чек-лист релиза. Дополняет `RULES.md § 2.9`
(документация) и `RULES.md § 6.4` (формат commit message).

**Типы релизов** (Semantic Versioning):
- **Major** (`X.0.0`) — новая крупная фаза/платформа (v1.0.0 — продакшн-релиз).
- **Minor** (`0.X.0`) — новая функциональность, обратносовместимая (v0.1.0 — Design & Foundation).
- **Patch** (`0.1.X`) — багфиксы, документация.

---

## § 1. Подготовка (за 1 день до релиза)

- [ ] Все запланированные PL закрыты (Fixed) или перенесены.
- [ ] Все запланированные спринты завершены; отчёты по `RULES.md § 2.14`.
- [ ] `ruff check .` — 0 ошибок; `mypy packages apps/api` — 0 ошибок.
- [ ] `pytest` — все зелёные (live-тесты Skip).
- [ ] `flutter analyze` + `flutter test` — зелёные.
- [ ] CI на `main` — зелёный (последний коммит).
- [ ] Smoke-чеклист из [qa/MANUAL_TESTING_GUIDE.md](../qa/MANUAL_TESTING_GUIDE.md) § 2 пройден.

---

## § 1a. Известные ограничения релиза v0.1.0

> **ОБЯЗАТЕЛЬНО прочитать перед деплоем.**

- Локальный режим: SQLite + `127.0.0.1`, без авторизации. Серверный режим
  (PostgreSQL + JWT) — **не входит** в v0.1.0.
- Парсер Пятёрочки чувствителен к антиботу; при CAPTCHA запуск останавливается
  (ADR-006). Для стабильного потока данных используйте ручной импорт CSV.
- Entity resolution: пороги 0.90/0.70 — эмпирические; требуется ручной review
  и оценка precision/recall перед обучением моделей.
- ML-модели (CLIP/SentenceTransformers) опциональны; без них работает
  лексический matching с меньшим quality.
- `apps/mobile` — debug-сборки; release-подпись Android — v0.2+.
- Legacy-Excel-скрипты остаются в корне (PL-001) и не являются частью API.

---

## § 2. Обновление документации (в одном коммите)

| Файл | Что менять |
|---|---|
| `pyproject.toml` | `project.version = "X.Y.Z"` |
| `CHANGELOG.md` | `[Unreleased]` → `[X.Y.Z] — YYYY-MM-DD` + новая пустая `[Unreleased]` |
| `README.md` | заголовок версии, статус, ссылки |
| `docs/README.md` | версия документации |
| `docs/development/RULES.md` | § 8 (история правил), если добавлялись правила |
| `docs/KNOWN_ISSUES.md` | сводка по статусам |
| `docs/development/ARCHITECTURE.md` | версия, новые слои/ADR |
| `docs/development/vX.Y/DESIGN*.md` | финальная версия дизайна |

**Не трогать:** никаких дублей версии в коде (RULES § 1.11) — версия читается
из `importlib.metadata.version("pricescope-core")` / `__version__` пакета.

---

## § 3. Локальная сборка и проверка

```powershell
cd <repo-root>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ruff check .
mypy packages apps/api
# human_requests на Python 3.11 ломает автозагрузку pytest-плагинов (PL-009):
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q -p pytest_asyncio.plugin
pricescope init-db
pricescope parse --store lenta --lat 55.3925 --lon 36.7323
pricescope serve --local
# http://127.0.0.1:8765/health → {"status":"ok",...}
```

Flutter (проверка отдельно):

```powershell
cd apps/mobile
flutter pub get
flutter analyze
flutter test
flutter build web --dart-define=API_BASE_URL=http://127.0.0.1:8765
```

---

## § 4. Коммит

```powershell
git add -A
git status
@'
chore(release): vX.Y.Z — <тип> (PL-1, PL-2, ...)

- pyproject.toml: version X.Y.Z-1 -> X.Y.Z
- CHANGELOG.md: [Unreleased] -> [X.Y.Z] — YYYY-MM-DD
- README.md / docs/README.md: версия
- RULES.md § 8, KNOWN_ISSUES.md: сводка

ruff/mypy 0/0. Tests N/N. Flutter analyze/test OK.
'@ | Out-File -FilePath .commit-msg.txt -Encoding utf8NoBOM
git commit -F .commit-msg.txt
Remove-Item .commit-msg.txt
git push origin main
```

---

## § 5. Тег

```powershell
git tag -a vX.Y.Z -m "vX.Y.Z — <краткое название>"
git push origin vX.Y.Z
```

---

## § 6. GitHub Release

Создать `.release-notes-vX.Y.Z.md` (gitignore) по шаблону:

```markdown
## Что нового

<1-2 абзаца — суть релиза>

### PL-XXX — <название>
- <bullet>

## Статистика

- PL: N Fixed, M Planned.
- Тесты: N/N. CI зелёный.

## Запуск локально

    pip install -e .
    pricescope serve --local

## Документация

- `docs/development/RULES.md`, `CHANGELOG.md`, `docs/qa/MANUAL_TESTING_GUIDE.md`
```

```powershell
gh release create vX.Y.Z --title "vX.Y.Z — <название>" --notes-file .release-notes-vX.Y.Z.md --verify-tag
Remove-Item .release-notes-vX.Y.Z.md
```

---

## § 7. Что пошло не так — как исправлять

| Проблема | Fix |
|---|---|
| Пропущен GitHub Release | `gh release create vX.Y.Z ... --verify-tag` ретроактивно |
| Пропущен тег | `git tag -a vX.Y.Z -m "..." <sha>` + push |
| Неправильная версия в `/health` | проверить `pyproject.toml`, пересобрать пакет |
| CI красный из-за docs | прогнать `scripts/ci/check-doc-links.ps1`, починить ссылки |
| Изменилась схема БД без миграции | новая Alembic-миграция, не редактировать старую |

---

## § 8. Ссылки

- `RULES.md § 2` — документация в коммите
- `RULES.md § 6.4` — формат commit
- `CHANGELOG.md` — Keep a Changelog
- [QA-чеклист](../qa/MANUAL_TESTING_GUIDE.md)
- [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/) · [Semantic Versioning](https://semver.org/lang/ru/)
