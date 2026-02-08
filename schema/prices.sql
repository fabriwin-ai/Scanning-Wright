CREATE TABLE IF NOT EXISTS price_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  site TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  category TEXT NOT NULL,
  location_country TEXT NOT NULL,
  location_region TEXT,
  location_city TEXT,
  price_value REAL NOT NULL,
  currency TEXT NOT NULL,
  is_promo INTEGER DEFAULT 0,
  collected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_price_items_site ON price_items(site);
CREATE INDEX IF NOT EXISTS idx_price_items_category ON price_items(category);
CREATE INDEX IF NOT EXISTS idx_price_items_location ON price_items(location_country, location_region, location_city);
CREATE INDEX IF NOT EXISTS idx_price_items_collected_at ON price_items(collected_at);
