# Scanning-Wright
filter discriminator

## Primeros pasos de automatización

1. **Definir sitios prioritarios**: se centraliza en `config/targets.yaml` con los sitios, rutas de categoría y ubicación base.
2. **Modelo de datos**: el esquema inicial está en `schema/prices.sql` para persistir precios filtrados.
3. **Crawler base con Playwright**: `automation/price_scraper.py` implementa el flujo mínimo de extracción y filtrado.
4. **Ecosistema de interfaz y filtros**: el YAML ahora incluye selectores y filtros UI por sitio, además de la configuración de navegador y rate limiting.
8. **Escalabilidad y robustez**: se incorporan user agents rotativos, reintentos y esperas entre páginas.

## Uso rápido

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python automation/price_scraper.py --config config/targets.yaml
```

Los resultados se guardan en `data/price_results.json`, la base local en `data/prices.sqlite`,
y el reporte agregado en `data/report.md`.

## Dashboard

La interfaz visual vive en `dashboard/index.html` y ofrece un HUD minimalista para monitorear
el ecosistema de filtrado (precios, categorías y ubicaciones).
