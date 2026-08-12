# superset_config.py -- Konfigurasi tambahan Superset
# Dimount ke /app/pythonpath/superset_config.py (otomatis ke-load Superset saat start)

FEATURE_FLAGS = {
    # Wajib untuk Row-Level Security berbasis Jinja (current_username(), dsb).
    # Tanpa ini, {{ current_username() }} di RLS clause tidak pernah dirender
    # dan diperlakukan sebagai teks literal -- RLS jadi selalu 0 baris / bocor.
    "ENABLE_TEMPLATE_PROCESSING": True,
}

# Wajib kalau Superset diakses lewat reverse proxy (Nginx + HTTPS) supaya
# redirect/cookie/CSRF pakai scheme & host yang benar (https, domain asli),
# bukan http://127.0.0.1:8088 dari sudut pandang container.
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {"x_for": 1, "x_proto": 1, "x_host": 1, "x_port": 1, "x_prefix": 1}
