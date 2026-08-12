# setup_rbac.py -- Setup RBAC + Row-Level Security untuk Dashboard IKU
#
# Jalankan SEKALI setelah database & dashboard/dataset (superset_export.zip) di-import:
#   docker exec -i superset_app superset shell < setup_rbac.py
#
# Idempotent -- aman dijalankan ulang, skip apa yang sudah ada.
# Password akun demo di bawah HARUS diganti sebelum dipakai di lingkungan produksi nyata
# (ini cuma untuk staging/demo dengan data dummy).

import json
import os
import psycopg2
from superset import db, security_manager as sm
from superset.connectors.sqla.models import SqlaTable
from superset.connectors.sqla.models import RowLevelSecurityFilter
from flask_appbuilder.security.sqla.models import User, Role


# ---------------------------------------------------------------------
# 0. Pastikan semua 22 tabel + 6 view sudah terdaftar sebagai Dataset
#    (superset_export.zip cuma bawa dataset yang dipakai chart; sisanya
#    dilengkapi di sini supaya semua tabel schema.sql punya Dataset).
# ---------------------------------------------------------------------
ALL_TABLES = [
    "faculties", "programs", "lecturers", "dashboard_users",
    "admission_funnel", "retention", "student_enrollment", "graduation", "demographics",
    "iku1_aee", "iku2_tracer_study", "iku3_aktivitas_mahasiswa", "iku5_kerjasama", "iku7_sdgs",
    "iku9_pendapatan_non_ukt", "iku9_pendapatan_ukt", "iku12_kesejahteraan_dosen",
    "iku4_rekognisi_dosen", "iku6_publikasi", "iku8_sdm_kebijakan", "iku11_tata_kelola", "iku_target",
    "v_iku1_aee", "v_iku2_terserap", "v_iku3_aktivitas", "v_iku5_hilirisasi", "v_iku9_non_ukt", "v_iku12_kesejahteraan",
]

database = db.session.query(__import__("superset.models.core", fromlist=["Database"]).Database).filter_by(database_name="PostgreSQL").first()

for name in ALL_TABLES:
    exists = db.session.query(SqlaTable).filter_by(table_name=name, database_id=database.id).first()
    if exists:
        continue
    t = SqlaTable(table_name=name, database=database, schema="public")
    db.session.add(t)
    db.session.commit()
    t.fetch_metadata()
    db.session.commit()
    print("dataset created:", name)

print("STEP0_DATASETS_OK")


# ---------------------------------------------------------------------
# 1. Role: Rektor, Dekan, Kaprodi, + 4 sub-role Kabag per bureau
# ---------------------------------------------------------------------
gamma = sm.find_role("Gamma")
gamma_perms = list(gamma.permissions)

role_names = ["Rektor", "Dekan", "Kaprodi", "Kabag Akademik", "Kabag Admisi", "Kabag Keuangan", "Kabag SDM"]
roles = {}

for rn in role_names:
    r = sm.find_role(rn)
    if r is None:
        r = sm.add_role(rn)
    r.permissions = gamma_perms
    roles[rn] = r

db.session.commit()
print("STEP1_ROLES_OK", list(roles.keys()))

all_ds_pv = sm.add_permission_view_menu("all_datasource_access", "all_datasource_access")
roles["Rektor"].permissions = list(roles["Rektor"].permissions) + [all_ds_pv]
roles["Dekan"].permissions = list(roles["Dekan"].permissions) + [all_ds_pv]
roles["Kaprodi"].permissions = list(roles["Kaprodi"].permissions) + [all_ds_pv]
db.session.commit()
print("STEP1B_ALL_DATASOURCE_ACCESS_OK")

kabag_domain = {
    "Kabag Akademik": ["student_enrollment", "admission_funnel", "retention", "graduation", "demographics",
                        "iku1_aee", "iku2_tracer_study", "iku3_aktivitas_mahasiswa",
                        "v_iku1_aee", "v_iku2_terserap", "v_iku3_aktivitas", "programs", "faculties"],
    "Kabag Admisi": ["admission_funnel", "demographics", "programs", "faculties"],
    "Kabag Keuangan": ["iku9_pendapatan_non_ukt", "iku9_pendapatan_ukt", "v_iku9_non_ukt"],
    "Kabag SDM": ["lecturers", "iku12_kesejahteraan_dosen", "iku4_rekognisi_dosen",
                  "iku6_publikasi", "iku8_sdm_kebijakan", "v_iku12_kesejahteraan"],
}

for role_name, table_names in kabag_domain.items():
    role = roles[role_name]
    extra_perms = []
    for tname in table_names:
        t = db.session.query(SqlaTable).filter_by(table_name=tname).first()
        pv = sm.add_permission_view_menu("datasource_access", t.get_perm())
        extra_perms.append(pv)
    role.permissions = list(role.permissions) + extra_perms

db.session.commit()
print("STEP1C_KABAG_DATASET_ACCESS_OK")


# ---------------------------------------------------------------------
# 2. Akun demo per baris dashboard_users (password sama untuk semua --
#    GANTI kalau dipakai di luar staging/demo)
# ---------------------------------------------------------------------
DEMO_PASSWORD = "Demo@12345"

conn = psycopg2.connect(
    host="db", port=5432,
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
cur = conn.cursor()
cur.execute("SELECT username, role, faculty_id, program_id, bureau FROM dashboard_users ORDER BY username")
rows = cur.fetchall()
conn.close()

bureau_role_map = {"akademik": "Kabag Akademik", "admisi": "Kabag Admisi", "keuangan": "Kabag Keuangan", "sdm": "Kabag SDM"}

created = []
for username, role, faculty_id, program_id, bureau in rows:
    if role == "rektor":
        superset_role_name = "Rektor"
    elif role == "dekan":
        superset_role_name = "Dekan"
    elif role == "kaprodi":
        superset_role_name = "Kaprodi"
    else:
        superset_role_name = bureau_role_map[bureau]
    superset_role = sm.find_role(superset_role_name)
    if sm.find_user(username=username):
        continue
    scope_label = faculty_id or program_id or bureau or "ALL"
    sm.add_user(
        username=username, first_name=role.capitalize(), last_name=scope_label,
        email=username + "@dashboard-iku.local", role=superset_role, password=DEMO_PASSWORD,
    )
    created.append(username)

print("STEP2_USERS_OK", created)


# ---------------------------------------------------------------------
# 3. Row-Level Security -- perlu ENABLE_TEMPLATE_PROCESSING aktif
#    (lihat superset_config.py), kalau tidak {{ current_username() }}
#    tidak akan pernah dirender dan RLS jadi 0 baris / bocor.
# ---------------------------------------------------------------------

def get_tables(names):
    return [db.session.query(SqlaTable).filter_by(table_name=n).first() for n in names]


CLAUSE_PROGRAM_BY_FACULTY = "program_id IN (SELECT program_id FROM programs WHERE faculty_id = (SELECT faculty_id FROM dashboard_users WHERE username = '{{ current_username() }}'))"
CLAUSE_PROGRAM_DIRECT = "program_id = (SELECT program_id FROM dashboard_users WHERE username = '{{ current_username() }}')"
CLAUSE_KERJASAMA_BY_FACULTY = "program_terkait_id IN (SELECT program_id FROM programs WHERE faculty_id = (SELECT faculty_id FROM dashboard_users WHERE username = '{{ current_username() }}'))"
CLAUSE_KERJASAMA_DIRECT = "program_terkait_id = (SELECT program_id FROM dashboard_users WHERE username = '{{ current_username() }}')"
CLAUSE_FACULTY_DIRECT = "faculty_id = (SELECT faculty_id FROM dashboard_users WHERE username = '{{ current_username() }}')"
CLAUSE_UNIT_BY_FACULTY = "(unit_pelaksana = (SELECT faculty_id FROM dashboard_users WHERE username = '{{ current_username() }}') OR unit_pelaksana = 'GEN')"
CLAUSE_HIDE = "1=0"

rls_specs = [
    ("RLS Dekan - tabel by program (via faculty)", ["Dekan"], CLAUSE_PROGRAM_BY_FACULTY,
     ["student_enrollment", "admission_funnel", "retention", "graduation", "demographics",
      "iku1_aee", "iku2_tracer_study", "iku3_aktivitas_mahasiswa", "iku12_kesejahteraan_dosen",
      "iku4_rekognisi_dosen", "iku6_publikasi", "iku8_sdm_kebijakan", "lecturers"]),
    ("RLS Kaprodi - tabel by program", ["Kaprodi"], CLAUSE_PROGRAM_DIRECT,
     ["student_enrollment", "admission_funnel", "retention", "graduation", "demographics",
      "iku1_aee", "iku2_tracer_study", "iku3_aktivitas_mahasiswa", "iku12_kesejahteraan_dosen",
      "iku4_rekognisi_dosen", "iku6_publikasi", "iku8_sdm_kebijakan", "lecturers"]),
    ("RLS Dekan - kerjasama by program (via faculty)", ["Dekan"], CLAUSE_KERJASAMA_BY_FACULTY, ["iku5_kerjasama"]),
    ("RLS Kaprodi - kerjasama by program", ["Kaprodi"], CLAUSE_KERJASAMA_DIRECT, ["iku5_kerjasama"]),
    ("RLS Dekan+Kaprodi - SDGs by faculty", ["Dekan", "Kaprodi"], CLAUSE_UNIT_BY_FACULTY, ["iku7_sdgs"]),
    ("RLS Dekan - view indikator by faculty", ["Dekan"], CLAUSE_FACULTY_DIRECT,
     ["v_iku1_aee", "v_iku2_terserap", "v_iku3_aktivitas", "v_iku12_kesejahteraan"]),
    ("RLS Kaprodi - view indikator by program", ["Kaprodi"], CLAUSE_PROGRAM_DIRECT,
     ["v_iku1_aee", "v_iku2_terserap", "v_iku3_aktivitas", "v_iku12_kesejahteraan"]),
    ("RLS Dekan+Kaprodi - sembunyikan data institusional", ["Dekan", "Kaprodi"], CLAUSE_HIDE,
     ["iku9_pendapatan_non_ukt", "iku9_pendapatan_ukt", "v_iku9_non_ukt", "v_iku5_hilirisasi"]),
]

rls_created = []
for name, role_names_, clause, table_names in rls_specs:
    if db.session.query(RowLevelSecurityFilter).filter_by(name=name).first():
        continue
    f = RowLevelSecurityFilter(
        name=name, filter_type="Regular", clause=clause,
        roles=[sm.find_role(rn) for rn in role_names_],
        tables=get_tables(table_names),
    )
    db.session.add(f)
    rls_created.append(name)

db.session.commit()
print("STEP3_RLS_OK", rls_created)

print("SETUP_RBAC_COMPLETE")
