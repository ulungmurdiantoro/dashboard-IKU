# superset_config.py -- Konfigurasi tambahan Superset
# Dimount ke /app/pythonpath/superset_config.py (otomatis ke-load Superset saat start)

FEATURE_FLAGS = {
    # Wajib untuk Row-Level Security berbasis Jinja (current_username(), dsb).
    # Tanpa ini, {{ current_username() }} di RLS clause tidak pernah dirender
    # dan diperlakukan sebagai teks literal -- RLS jadi selalu 0 baris / bocor.
    "ENABLE_TEMPLATE_PROCESSING": True,
}
