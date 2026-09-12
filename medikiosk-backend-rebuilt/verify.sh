#!/usr/bin/env bash
# Pre-flight check. Run this before uvicorn — it catches the failures that
# otherwise surface as a 500 halfway through a demo.
set -e
cd "$(dirname "$0")"

echo "1/5  Python syntax"
find app scripts tests -name "*.py" -print0 | xargs -0 python3 -m py_compile
echo "     ok"

echo "2/5  Pathway files"
python3 -c "from app.services.questioning.schema import load_pathways; p=load_pathways(); print(f'     {len(p)} pathways: {\", \".join(sorted(p))}')"

echo "3/5  Settings load"
python3 -c "from app.core.config import settings; print(f'     env={settings.ENV} ai={settings.AI_PROVIDER} ocr={settings.OCR_PROVIDER} storage={settings.STORAGE_PROVIDER}')"

echo "4/5  Models import (Alembic sees all tables)"
python3 -c "from app.models import Base; print(f'     {len(Base.metadata.tables)} tables registered')"

echo "5/5  App builds"
python3 -c "from app.main import app; print(f'     {len(app.routes)} routes')"

echo
echo "All checks passed."
