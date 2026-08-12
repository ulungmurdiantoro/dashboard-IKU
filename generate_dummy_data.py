"""
Generator data dummy untuk Dashboard IR + IKU Kemdiktisaintek.
Konsisten dengan skema Sampoerna University (12 prodi, 6 fakultas)
yang sudah dipakai di mockup/POC sebelumnya.

Cara pakai:
    pip install faker --break-system-packages   # opsional, untuk nama mitra/dosen lebih variatif
    python3 generate_dummy_data.py

Output: folder ./output berisi CSV per tabel, siap di-upload ke Superset
(Data > Upload CSV) atau di-import ke PostgreSQL via COPY.
"""

import csv
import os
import random

random.seed(20260810)  # reproducible

OUT = "output"
os.makedirs(OUT, exist_ok=True)

YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
GRAD_YEARS = YEARS

FACULTIES = {
    "FBE":  "Faculty of Business",
    "FST":  "Faculty of Engineering & Technology",
    "FOE":  "Faculty of Education",
    "FADM": "Faculty of Art, Design & Media",
    "FSS":  "Faculty of Arts & Science",
    "GEN":  "General / Undecided",
}

PROGRAMS = [
    ("ACC", "Accounting", "FBE", 520),
    ("MGT", "Management", "FBE", 610),
    ("CS",  "Computer Science", "FST", 780),
    ("IS",  "Information System", "FST", 430),
    ("IE",  "Industrial Engineering", "FST", 340),
    ("ME",  "Mechanical Engineering", "FST", 300),
    ("MTE", "Mathematics Education", "FOE", 210),
    ("ELE", "English Language Education", "FOE", 250),
    ("ELT", "English Language Teaching", "FOE", 180),
    ("VCD", "Visual Communication Design", "FADM", 470),
    ("PSY", "Psychology", "FSS", 560),
    ("UND", "Undecided (Other)", "GEN", 120),
]

def w(filename, header, rows):
    path = os.path.join(OUT, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {filename}: {len(rows)} rows")

def rfloat(a, b, nd=2):
    return round(random.uniform(a, b), nd)

# ---------------------------------------------------------------
print("== Bagian 0: Referensi ==")

w("faculties.csv", ["faculty_id", "name", "short_name"],
  [(fid, name, fid) for fid, name in FACULTIES.items()])

w("programs.csv", ["program_id", "name", "faculty_id", "jenjang"],
  [(pid, name, fac, "S1") for pid, name, fac, base in PROGRAMS])

JABATAN = ["Asisten Ahli", "Lektor", "Lektor Kepala", "Guru Besar"]
lecturers = []
lid = 1
for pid, name, fac, base in PROGRAMS:
    n_dosen = max(4, round(base / 60))
    for i in range(n_dosen):
        lecturers.append((
            f"D{lid:04d}", f"Dosen {lid:04d}", pid,
            random.choices(JABATAN, weights=[35, 40, 20, 5])[0],
            random.choices(["Sudah", "Belum"], weights=[70, 30])[0],
            random.choices(["S2", "S3"], weights=[65, 35])[0],
            random.randint(2005, 2024),
        ))
        lid += 1
w("lecturers.csv",
  ["dosen_id", "name", "program_id", "jabatan_akademik",
   "status_sertifikasi", "pendidikan_terakhir", "tahun_mulai_kerja"],
  lecturers)

# RBAC users - contoh 1 akun per peran
dashboard_users = [
    ("rektor", "rektor", "", "", ""),
]
for fid in FACULTIES:
    dashboard_users.append((f"dekan_{fid.lower()}", "dekan", fid, "", ""))
for pid, name, fac, base in PROGRAMS:
    dashboard_users.append((f"kaprodi_{pid.lower()}", "kaprodi", fac, pid, ""))
dashboard_users.append(("kabag_akademik", "kabag", "", "", "akademik"))
dashboard_users.append(("kabag_admisi", "kabag", "", "", "admisi"))
w("dashboard_users.csv",
  ["username", "role", "faculty_id", "program_id", "bureau"],
  dashboard_users)

# ---------------------------------------------------------------
print("== Bagian 1: Modul IR inti ==")

admission_funnel = []
for pid, name, fac, base in PROGRAMS:
    for i, y in enumerate(YEARS):
        growth = 1 + i * 0.045 + rfloat(-0.05, 0.07, 3)
        complete = max(15, round(base / 6 * growth))
        admitted = round(complete * rfloat(0.68, 0.86, 3))
        enrolled = round(admitted * rfloat(0.52, 0.74, 3))
        admission_funnel.append((pid, y, complete, admitted, enrolled))
w("admission_funnel.csv",
  ["program_id", "year", "complete", "admitted", "enrolled"], admission_funnel)

demographics = []
for pid, name, fac, base in PROGRAMS:
    for y in YEARS:
        male = random.randint(38, 62)
        jkt, jabar = random.randint(28, 42), random.randint(12, 20)
        other = random.randint(20, 35)
        intl = max(1, 100 - jkt - jabar - other)
        assisted = random.randint(30, 55)
        demographics.append((
            pid, y, male, 100 - male, jkt, jabar, other, intl,
            100 - assisted, assisted
        ))
w("demographics.csv",
  ["program_id", "year", "male_pct", "female_pct", "region_jkt_pct",
   "region_jabar_pct", "region_other_pct", "region_intl_pct",
   "fee_paying_pct", "assisted_pct"], demographics)

graduation = []
for pid, name, fac, base in PROGRAMS:
    for i, y in enumerate(GRAD_YEARS):
        grad_count = max(4, round((base / 9) * (1 + i * 0.05) + rfloat(-3, 4, 1)))
        graduation.append((
            pid, y, grad_count, rfloat(3.05, 3.72), random.randint(70, 90),
            100 - random.randint(70, 90), rfloat(3.9, 4.6)
        ))
w("graduation.csv",
  ["program_id", "grad_year", "grad_count", "avg_gpa", "ftic_pct",
   "transfer_pct", "avg_years"], graduation)

retention = []
for pid, name, fac, base in PROGRAMS:
    for y in YEARS:
        y1 = max(10, round(base / 6))
        rate = rfloat(0.80, 0.97, 3)
        retention.append((pid, y, y1, round(y1 * rate), rate))
w("retention.csv",
  ["program_id", "year", "year1_count", "year2_count", "rate"], retention)

# ---------------------------------------------------------------
print("== Bagian 2: 7 IKU Wajib ==")

iku1 = []
for pid, name, fac, base in PROGRAMS:
    for y in GRAD_YEARS:
        total = max(4, round(base / 9))
        tepat = round(total * rfloat(0.55, 0.85))
        iku1.append((pid, y, tepat, total, 8))
w("iku1_aee.csv",
  ["program_id", "tahun_lulus", "lulus_tepat_waktu", "lulus_total",
   "standar_masa_studi_semester"], iku1)

iku2 = []
for pid, name, fac, base in PROGRAMS:
    for y in GRAD_YEARS:
        total = max(4, round(base / 9))
        responden = round(total * rfloat(0.6, 0.95))
        bekerja = round(responden * rfloat(0.55, 0.75))
        wirausaha = round(responden * rfloat(0.05, 0.15))
        lanjut = round(responden * rfloat(0.05, 0.15))
        belum = max(0, responden - bekerja - wirausaha - lanjut)
        iku2.append((pid, y, responden, bekerja, wirausaha, lanjut, belum,
                      rfloat(2.0, 8.0, 1)))
w("iku2_tracer_study.csv",
  ["program_id", "tahun_lulus", "jumlah_responden", "bekerja", "wirausaha",
   "lanjut_studi", "belum_bekerja", "waktu_tunggu_rata2_bulan"], iku2)

iku3 = []
for pid, name, fac, base in PROGRAMS:
    for y in YEARS:
        active_pool = max(20, round(base / 4))
        iku3.append((
            pid, y,
            random.randint(5, round(active_pool * 0.3) + 5),
            random.randint(1, round(active_pool * 0.1) + 2),
            random.randint(0, 8),
            random.randint(2, round(active_pool * 0.15) + 3),
            random.randint(10, round(active_pool * 0.5) + 10),
            random.randint(2, 15),
        ))
w("iku3_aktivitas_mahasiswa.csv",
  ["program_id", "tahun", "ikut_kompetisi", "menang_prestasi",
   "ikut_pertukaran_pelajar", "ikut_riset_dosen", "ikut_organisasi",
   "ikut_pengabdian"], iku3)

MITRA_POOL = [
    ("PT Astra International", "Industri"), ("Bank Mandiri", "Industri"),
    ("Kemendikbudristek", "Pemerintah"), ("Pemkot Bekasi", "Pemerintah"),
    ("SMA Labschool Jakarta", "Sekolah"), ("SMK Telkom", "Sekolah"),
    ("Tokopedia", "Industri"), ("Traveloka", "Industri"),
    ("Yayasan Cinta Anak Bangsa", "Lembaga"), ("Kadin Indonesia", "Lembaga"),
    ("Google Indonesia", "Industri"), ("UNDP Indonesia", "Lembaga"),
]
iku5 = []
kid = 1
for pid, name, fac, base in PROGRAMS:
    n = random.randint(2, 5)
    for _ in range(n):
        mitra, jenis = random.choice(MITRA_POOL)
        start = random.choice(YEARS)
        status = random.choices(["Aktif", "Selesai"], weights=[70, 30])[0]
        akhir = "" if status == "Aktif" else start + random.randint(1, 2)
        iku5.append((
            kid, mitra, jenis, pid, start, akhir, status,
            random.choices([True, False], weights=[55, 45])[0],
            "Kolaborasi program magang dan riset terapan" if jenis == "Industri"
            else "Program pengabdian dan pelatihan bersama"
        ))
        kid += 1
w("iku5_kerjasama.csv",
  ["kerjasama_id", "nama_mitra", "jenis_mitra", "program_terkait_id",
   "tahun_mulai", "tahun_berakhir", "status", "ada_hilirisasi",
   "deskripsi_dampak"], iku5)

SDG_LIST = ["SDG 1", "SDG 3", "SDG 4", "SDG 8", "SDG 9", "SDG 10", "SDG 17"]
iku7 = []
gid = 1
for fid in FACULTIES:
    for y in YEARS:
        n = random.randint(1, 3)
        for _ in range(n):
            iku7.append((
                gid, f"Program Pengabdian Masyarakat {fid} {y}-{gid}",
                random.choice(SDG_LIST), y, fid, random.randint(30, 500)
            ))
            gid += 1
w("iku7_sdgs.csv",
  ["kegiatan_id", "judul", "sdg_terkait", "tahun", "unit_pelaksana",
   "jumlah_penerima_manfaat"], iku7)

SUMBER_NON_UKT = ["Bisnis Kampus", "Pelatihan & Sertifikasi", "Konsultasi",
                   "Hibah Penelitian", "Kerjasama Industri", "Unit Usaha Kampus"]
iku9 = []
nid = 1
for y in YEARS:
    for sumber in SUMBER_NON_UKT:
        base_amt = random.randint(150, 900) * 1_000_000
        growth = 1 + (y - 2021) * 0.08
        iku9.append((nid, y, sumber, round(base_amt * growth)))
        nid += 1
w("iku9_pendapatan_non_ukt.csv",
  ["id", "tahun", "sumber", "jumlah_rupiah"], iku9)

iku12 = []
TUNJANGAN = ["Fungsional", "Sertifikasi Dosen", "Kinerja", "Tidak Ada"]
for dosen in lecturers:
    dosen_id = dosen[0]
    for y in YEARS:
        iku12.append((
            dosen_id, y,
            random.choices(TUNJANGAN, weights=[30, 35, 25, 10])[0],
            random.choices([True, False], weights=[60, 40])[0],
            random.choices(
                ["BPJS Kesehatan & Ketenagakerjaan", "BPJS Kesehatan saja", "Tidak Ada"],
                weights=[70, 20, 10])[0],
        ))
w("iku12_kesejahteraan_dosen.csv",
  ["dosen_id", "tahun", "kategori_tunjangan", "ikut_pengembangan_karir",
   "status_perlindungan"], iku12)

# ---------------------------------------------------------------
print("== Bagian 3: 4 IKU Pilihan (opsional) ==")

REKOGNISI = ["Penghargaan Internasional", "Kepakaran Nasional",
             "Sitasi Ilmiah Tinggi", "Penerapan Riset di Masyarakat"]
iku4 = []
rid = 1
for dosen in random.sample(lecturers, k=max(5, len(lecturers)//4)):
    y = random.choice(YEARS)
    iku4.append((rid, dosen[0], y, random.choice(REKOGNISI),
                  "Pengakuan atas kontribusi keilmuan dan riset terapan"))
    rid += 1
w("iku4_rekognisi_dosen.csv",
  ["id", "dosen_id", "tahun", "jenis_rekognisi", "deskripsi"], iku4)

iku6 = []
pubid = 1
for dosen in lecturers:
    n_pub = random.choices([0, 1, 2, 3], weights=[30, 35, 25, 10])[0]
    for _ in range(n_pub):
        y = random.choice(YEARS)
        iku6.append((
            pubid, dosen[0], y, f"Studi terapan bidang {dosen[2]} tahun {y}",
            random.choices(["Scopus", "WoS", "Lainnya"], weights=[55, 20, 25])[0],
            random.randint(0, 40)
        ))
        pubid += 1
w("iku6_publikasi.csv",
  ["id", "dosen_id", "tahun", "judul", "indeks", "jumlah_sitasi"], iku6)

iku8 = []
sid = 1
for dosen in random.sample(lecturers, k=max(3, len(lecturers)//6)):
    y = random.choice(YEARS)
    iku8.append((sid, dosen[0], y,
                  random.choice(["Penyusunan Kebijakan", "Konsultasi Pemerintah",
                                  "Konsultasi Industri"]),
                  random.choice(["Kemendikbudristek", "Pemkot", "Kadin", "OJK"])))
    sid += 1
w("iku8_sdm_kebijakan.csv",
  ["id", "dosen_id", "tahun", "jenis_keterlibatan", "instansi"], iku8)

iku11 = []
tid = 1
for y in YEARS:
    for kat in ["Audit Keuangan", "SAKIP", "Integritas Akademik", "Anti Korupsi"]:
        iku11.append((tid, y, kat, random.choice(["Baik", "Sangat Baik", "Cukup"])))
        tid += 1
w("iku11_tata_kelola.csv",
  ["id", "tahun", "kategori", "skor_atau_status"], iku11)

print("\nSelesai. Semua file CSV ada di folder ./output/")
