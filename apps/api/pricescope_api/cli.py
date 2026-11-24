"""CLI `pricescope`: init-db, parse, serve, export."""

from __future__ import annotations

import argparse
import asyncio
import sys

from pricescope_api import __version__
from pricescope_api.config import get_settings
from pricescope_api.db.session import get_sessionmaker, init_db
from pricescope_api.logging import configure_logging, new_trace_id
from pricescope_api.services import export_dataset, run_import


def build_parser() -> argparse.ArgumentParser:
    """Построить парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(prog="pricescope", description="PriceScope CLI")
    parser.add_argument("--version", action="version", version=f"pricescope {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="создать схему БД")

    parse = sub.add_parser("parse", help="запустить парсер магазина")
    parse.add_argument("--store", required=True, help="lenta | pyaterochka | manual")
    parse.add_argument("--lat", type=float, default=None)
    parse.add_argument("--lon", type=float, default=None)
    parse.add_argument("--category", action="append", dest="categories")
    parse.add_argument("--file", dest="csv_file", help="CSV для store=manual")
    parse.add_argument("--details", action="store_true", help="дозапрос деталей/фото")
    parse.add_argument("--limit", type=int, default=None, help="максимум товаров (smoke/отладка)")
    parse.add_argument("--idempotency-key")

    serve = sub.add_parser("serve", help="поднять API и просмотровщик")
    serve.add_argument("--local", action="store_true", help="локальный режим (SQLite, 127.0.0.1)")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    photos = sub.add_parser("fetch-photos", help="дозагрузить фото по URL из БД")
    photos.add_argument("--limit", type=int, default=None, help="максимум observation за запуск")
    photos.add_argument("--concurrency", type=int, default=8, help="параллельные загрузки")

    legacy = sub.add_parser("import-legacy", help="импортировать legacy Excel и фото")
    legacy.add_argument(
        "--excel",
        default=None,
        help="путь к lenta_prices.xlsx (по умолчанию — корень проекта)",
    )
    legacy.add_argument(
        "--photos",
        default=None,
        help="каталог photos/{id}.png (по умолчанию — корень проекта)",
    )
    legacy.add_argument("--store", default="lenta", help="код магазина в БД")

    export = sub.add_parser("export", help="выгрузить датасет")
    export.add_argument("--name", default="product-matching")
    export.add_argument("--version", dest="dataset_version", default="1")

    match_parser = sub.add_parser("match", help="сопоставление товаров")
    match_parser.add_argument("--review", action="store_true", help="очередь спорных пар")
    match_parser.add_argument("--run", action="store_true", help="запустить entity resolution")
    return parser


async def _async_command(args: argparse.Namespace) -> int:
    """Выполнить асинхронную часть команды."""
    settings = get_settings()
    new_trace_id()

    if args.command == "init-db":
        await init_db()
        print(f"БД инициализирована: {settings.db_path}")
        return 0

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        if args.command == "parse":
            categories = args.categories
            if args.store == "manual":
                if not args.csv_file:
                    print("--file обязателен для store=manual", file=sys.stderr)
                    return 2
                categories = [args.csv_file]
            result = await run_import(
                session,
                settings,
                args.store,
                lat=args.lat,
                lon=args.lon,
                categories=categories,
                fetch_details=args.details,
                idempotency_key=args.idempotency_key,
                limit=args.limit,
            )
            print(
                f"Импорт #{result['run_id']}: {result['status']} · "
                f"new={result['new']} updated={result['updated']} skipped={result['skipped']} "
                f"trace={result['trace_id']}"
            )
            if result.get("error_code"):
                print(f"Ошибка: {result['error_code']} — {result.get('error_message') or ''}")
                return 1
            return 0

        if args.command == "fetch-photos":
            from pricescope_api.services import fetch_photos

            result = await fetch_photos(
                session, settings, limit=args.limit, concurrency=args.concurrency
            )
            print(
                f"Фото: скачано={result['downloaded']} уже было={result['reused']} "
                f"локальных={result['already_local']} ошибок={result['failed']} "
                f"без источника={result['no_source']}"
            )
            return 0

        if args.command == "import-legacy":
            from pathlib import Path

            from pricescope_api.config import PROJECT_ROOT
            from pricescope_api.legacy_import import import_legacy_excel

            excel_path = Path(args.excel) if args.excel else PROJECT_ROOT / "lenta_prices.xlsx"
            photos_dir = Path(args.photos) if args.photos else PROJECT_ROOT / "photos"
            result = await import_legacy_excel(
                session,
                excel_path=excel_path,
                photos_dir=photos_dir,
                store_code=args.store,
            )
            print(
                f"Импорт {excel_path.name}: new={result['new']} updated={result['updated']} "
                f"unchanged={result['unchanged']} skipped={result['skipped']} "
                f"raw_ref={result['raw_ref'][:12]}…"
            )
            return 0

        if args.command == "export":
            result = await export_dataset(
                session, settings, args.name, args.dataset_version
            )
            print(f"Датасет: {result['path']}")
            return 0

        if args.command == "match":
            from sqlalchemy import select

            from pricescope_api.db.models import ProductMatch
            from pricescope_api.services import run_matching

            if args.run:
                result = await run_matching(session)
                counts = result["counts"]
                print(
                    f"Сопоставление: auto={counts['auto']} review={counts['review']} "
                    f"new={counts['new']} ({result['model_version']})"
                )
                return 0

            stmt = select(ProductMatch)
            if args.review:
                stmt = stmt.where(ProductMatch.status == "review")
            rows = (await session.execute(stmt)).scalars().all()
            for match in rows:
                print(f"#{match.id} score={match.score:.2f} {match.status}")
            return 0
    return 0


def main() -> None:
    """Точка входа CLI."""
    args = build_parser().parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)

    if args.command == "serve":
        import uvicorn

        host = args.host or ("127.0.0.1" if args.local else settings.host)
        port = args.port or settings.port
        uvicorn.run("pricescope_api.app:app", host=host, port=port, reload=False)
        return

    raise SystemExit(asyncio.run(_async_command(args)))


if __name__ == "__main__":
    main()
