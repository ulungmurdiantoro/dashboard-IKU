# fix_dashboard_layouts.py -- Perbaiki posisi chart di dashboard yang "hilang"
# atau "ketuker" setelah import (superset_export.zip).
#
# Penyebab: file export menyimpan referensi chart pakai chartId numerik dari
# instance sumber. Di instance tujuan, chart yang sama bisa dapat ID berbeda
# saat di-import, jadi position_json dashboard jadi salah acu. Script ini
# menyusun ulang position_json dengan mencari chart berdasarkan NAMA (yang
# selalu benar), bukan ID.
#
# Jalankan setelah import-dashboards (script mandiri, BUKAN lewat "superset shell" --
# console interaktifnya kadang gagal parse function bersarang seperti di file ini):
#   docker exec superset_app python3 /tmp/fix_dashboard_layouts.py
#
# Aman dijalankan berkali-kali (idempotent).

import json
from superset.app import create_app

app = create_app()
app_ctx = app.app_context()
app_ctx.push()

from superset import db
from superset.models.slice import Slice
from superset.models.dashboard import Dashboard


def build_position(title, layout_rows, name_to_slice):
    position = {}
    position["DASHBOARD_VERSION_KEY"] = "v2"
    position["ROOT_ID"] = {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]}
    position["GRID_ID"] = {
        "type": "GRID", "id": "GRID_ID",
        "children": [r for r, _ in layout_rows],
        "parents": ["ROOT_ID"],
    }
    position["HEADER_ID"] = {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": title}}

    all_slices = []

    for row_id, entries in layout_rows:
        position[row_id] = {
            "type": "ROW", "id": row_id,
            "children": [e[0] for e in entries],
            "parents": ["ROOT_ID", "GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        for chart_key, slice_name, width, height in entries:
            slc = name_to_slice.get(slice_name)
            if slc is None:
                print("  MISSING CHART (skip):", slice_name)
                continue
            position[chart_key] = {
                "type": "CHART", "id": chart_key, "children": [],
                "parents": ["ROOT_ID", "GRID_ID", row_id],
                "meta": {"chartId": slc.id, "width": width, "height": height, "sliceName": slc.slice_name},
            }
            all_slices.append(slc)

    return position, all_slices


DASHBOARDS = [
    {
        "slug": "ir-inti",
        "title": "IR Inti - Admisi, Retensi, Distribusi",
        "layout": [
            ("ROW-1", [
                ("CHART-1", "KPI - Total Mahasiswa Aktif 2026", 4, 50),
                ("CHART-2", "KPI - Total Lulusan 2026", 4, 50),
                ("CHART-3", "KPI - Rata-rata Retensi 2026", 4, 50),
            ]),
            ("ROW-2", [
                ("CHART-4", "Funnel Admisi 2026", 6, 60),
                ("CHART-5", "Distribusi Mahasiswa Aktif per Fakultas 2026", 6, 60),
            ]),
            ("ROW-3", [
                ("CHART-6", "Tren Retensi per Tahun", 12, 60),
            ]),
        ],
    },
    {
        "slug": "iku-wajib",
        "title": "IKU Wajib - 7 Indikator Kinerja Utama",
        "layout": [
            ("ROW-SCORE", [("CHART-SCORE", "Scorecard Target 12 IKU 2026", 12, 50)]),
            ("ROW-IKU1", [
                ("CHART-IKU1A", "IKU1 - AEE per Prodi 2026", 6, 55),
                ("CHART-IKU1B", "IKU1 - Tren DO per Tahun", 6, 55),
            ]),
            ("ROW-IKU2", [
                ("CHART-IKU2A", "IKU2 - Komposisi Status Lulusan 2026", 6, 55),
                ("CHART-IKU2B", "IKU2 - Response Rate per Prodi 2026", 6, 55),
            ]),
            ("ROW-IKU3", [("CHART-IKU3A", "IKU3 - Tren Partisipasi per 100 Mahasiswa", 12, 55)]),
            ("ROW-IKU5", [
                ("CHART-IKU5A", "IKU5 - Mitra Aktif per Jenis 2026", 6, 55),
                ("CHART-IKU5B", "IKU5 - Hilirisasi Persen 2026", 6, 55),
            ]),
            ("ROW-IKU7", [("CHART-IKU7A", "IKU7 - Penerima Manfaat per SDG 2026", 12, 55)]),
            ("ROW-IKU9", [
                ("CHART-IKU9A", "IKU9 - Tren Pendapatan Non-UKT per Sumber", 8, 55),
                ("CHART-IKU9B", "IKU9 - Porsi Non-UKT 2026", 4, 55),
            ]),
            ("ROW-IKU12", [
                ("CHART-IKU12A", "IKU12 - Perlindungan Penuh 2026", 4, 55),
                ("CHART-IKU12B", "IKU12 - Pengembangan Karier per Fakultas 2026", 8, 55),
            ]),
        ],
    },
    {
        "slug": "iku-pilihan",
        "title": "IKU Pilihan - Rekognisi, Publikasi, SDM Kebijakan, Tata Kelola",
        "layout": [
            ("ROW-IKU4", [
                ("CHART-IKU4A", "IKU4 - Persen Dosen Rekognisi", 4, 55),
                ("CHART-IKU4B", "IKU4 - Rekognisi per Jenis dan Tingkat", 8, 55),
            ]),
            ("ROW-IKU6", [
                ("CHART-IKU6A", "IKU6 - Tren Publikasi per Tahun", 6, 55),
                ("CHART-IKU6B", "IKU6 - Sitasi per Prodi", 6, 55),
            ]),
            ("ROW-IKU8", [("CHART-IKU8A", "IKU8 - Keterlibatan SDM per Jenis", 12, 55)]),
            ("ROW-IKU11", [("CHART-IKU11A", "IKU11 - Skor Tata Kelola per Kategori dan Tahun", 12, 55)]),
        ],
    },
]

name_to_slice = {}
for s in db.session.query(Slice).all():
    name_to_slice[s.slice_name] = s

print("total charts found on this server:", len(name_to_slice))

for d in DASHBOARDS:
    dash = db.session.query(Dashboard).filter_by(slug=d["slug"]).first()
    if dash is None:
        print("SKIP (dashboard not found):", d["slug"])
        continue
    position, all_slices = build_position(d["title"], d["layout"], name_to_slice)
    dash.position_json = json.dumps(position)
    dash.slices = all_slices
    db.session.commit()
    print("FIXED:", d["slug"], "-> linked", len(all_slices), "charts")

print("FIX_DASHBOARD_LAYOUTS_DONE")
