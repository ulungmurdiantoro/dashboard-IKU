#!/usr/bin/env python3
"""
generate_dataset.py — Generator dataset dummy Dashboard IR + 12 IKU
====================================================================
Perbedaan utama dengan generator versi lama:

1. SATU SUMBER KEBENARAN. Seluruh angka akademik (pendaftar, diterima,
   mendaftar ulang, retensi, mahasiswa aktif, DO, lulusan) diturunkan dari
   satu simulasi kohor. Versi lama meng-generate tiap tabel secara acak dan
   independen, sehingga `graduation.grad_count` != `iku1_aee.lulus_total`
   pada 67 dari 72 baris, dan `retention.year1_count` != `admission_funnel.enrolled`
   pada 72 dari 72 baris.

2. TABEL BARU: student_enrollment (penyebut AEE + DO), iku9_pendapatan_ukt
   (pembanding IKU 9), iku11 diperluas jadi 6 komponen, iku_target (target &
   status wajib/pilihan per IKU per tahun).

Identitas yang dijamin skrip ini:
    mahasiswa_aktif(t+1) = mahasiswa_aktif(t) + mahasiswa_baru(t+1)
                           - lulus(t) - do_count(t)
    lulus_total          = lulus_tepat_waktu + lulus_terlambat
    graduation.grad_count = iku1_aee.lulus_total
    retention.year1_count = admission_funnel.enrolled

Jalankan:  python3 generate_dataset.py --out ./csv
"""

import argparse
import os
import random
from collections import defaultdict

import pandas as pd

SEED = 20260810
RNG = random.Random(SEED)

# Tahun yang dilaporkan di dashboard
YEAR_START, YEAR_END = 2021, 2026
REPORT_YEARS = list(range(YEAR_START, YEAR_END + 1))
# Kohor disimulasikan lebih awal supaya tahun 2021 sudah punya pipeline penuh
COHORT_YEARS = list(range(YEAR_START - 5, YEAR_END + 1))

STANDAR_MASA_STUDI_SEMESTER = 8  # S1 = 8 semester = 4 tahun

FACULTIES = [
    ("FBE", "Faculty of Business", "FBE"),
    ("FST", "Faculty of Engineering & Technology", "FST"),
    ("FOE", "Faculty of Education", "FOE"),
    ("FADM", "Faculty of Administration", "FADM"),
    ("FSS", "Faculty of Social Sciences", "FSS"),
]

PROGRAMS = [
    ("ACC", "Accounting", "FBE"),
    ("MGT", "Management", "FBE"),
    ("BIS", "Business Information Systems", "FBE"),
    ("CSE", "Computer Science", "FST"),
    ("EEE", "Electrical Engineering", "FST"),
    ("MEC", "Mechanical Engineering", "FST"),
    ("IND", "Industrial Engineering", "FST"),
    ("EDU", "Primary Education", "FOE"),
    ("ENG", "English Education", "FOE"),
    ("MTH", "Mathematics Education", "FOE"),
    ("PAD", "Public Administration", "FADM"),
    ("PSY", "Psychology", "FSS"),
]


# --------------------------------------------------------------------------
# 1. Parameter per program (tetap sepanjang simulasi, ditarik sekali dari seed)
# --------------------------------------------------------------------------
def build_program_params():
    params = {}
    for pid, _, _ in PROGRAMS:
        params[pid] = {
            "base_applicants": RNG.randint(90, 190),
            "growth": RNG.uniform(0.01, 0.07),      # pertumbuhan pendaftar / tahun
            "admit_rate": RNG.uniform(0.62, 0.85),  # selektivitas
            "yield_rate": RNG.uniform(0.52, 0.74),  # % diterima yang daftar ulang
            "r1": RNG.uniform(0.80, 0.93),          # survival tahun 1 -> 2
            "r2": RNG.uniform(0.92, 0.97),
            "r3": RNG.uniform(0.95, 0.99),
            "p_ontime": RNG.uniform(0.55, 0.82),    # % lulus tepat waktu (<= 8 smt)
            "gpa_base": RNG.uniform(3.15, 3.55),
            "ftic_base": RNG.randint(70, 90),       # % first-time-in-college
        }
    return params


# --------------------------------------------------------------------------
# 2. Simulasi kohor -> semua angka akademik
# --------------------------------------------------------------------------
def simulate(params):
    """Kembalikan dict berisi seluruh flow akademik per (program, tahun)."""
    admission = {}   # (pid, year) -> dict(complete, admitted, enrolled)
    cohorts = {}     # (pid, cohort_year) -> dict(n1..n5, g_ontime, g_late, do1..do5)

    for pid, _, _ in PROGRAMS:
        p = params[pid]
        for i, year in enumerate(COHORT_YEARS):
            trend = (1 + p["growth"]) ** i
            noise = RNG.uniform(0.90, 1.10)
            complete = int(round(p["base_applicants"] * trend * noise))
            admitted = int(round(complete * p["admit_rate"] * RNG.uniform(0.95, 1.05)))
            admitted = min(admitted, complete)
            enrolled = int(round(admitted * p["yield_rate"] * RNG.uniform(0.93, 1.07)))
            enrolled = max(15, min(enrolled, admitted))
            admission[(pid, year)] = {
                "complete": complete, "admitted": admitted, "enrolled": enrolled
            }

            # progresi kohor (bilangan bulat -> identitas neraca terjaga persis)
            n1 = enrolled
            n2 = int(round(n1 * p["r1"] * RNG.uniform(0.98, 1.02)))
            n2 = min(n2, n1)
            n3 = min(int(round(n2 * p["r2"])), n2)
            n4 = min(int(round(n3 * p["r3"])), n3)
            g_ontime = int(round(n4 * p["p_ontime"] * RNG.uniform(0.96, 1.04)))
            g_ontime = min(g_ontime, n4)
            n5 = n4 - g_ontime                      # lanjut ke tahun ke-5
            g_late = int(round(n5 * 0.85))
            do5 = n5 - g_late
            cohorts[(pid, year)] = {
                "n1": n1, "n2": n2, "n3": n3, "n4": n4, "n5": n5,
                "g_ontime": g_ontime, "g_late": g_late,
                "do1": n1 - n2, "do2": n2 - n3, "do3": n3 - n4, "do5": do5,
            }

    # Agregasi ke kalender.
    # Kohor c: thn studi 1 di kalender c, ... thn studi 5 di kalender c+4.
    # Lulus tepat waktu di akhir kalender c+3; lulus terlambat di akhir c+4.
    aktif = defaultdict(int)
    lulus_ontime = defaultdict(int)
    lulus_late = defaultdict(int)
    do_count = defaultdict(int)

    for (pid, c), k in cohorts.items():
        aktif[(pid, c)] += k["n1"]
        aktif[(pid, c + 1)] += k["n2"]
        aktif[(pid, c + 2)] += k["n3"]
        aktif[(pid, c + 3)] += k["n4"]
        aktif[(pid, c + 4)] += k["n5"]

        lulus_ontime[(pid, c + 3)] += k["g_ontime"]
        lulus_late[(pid, c + 4)] += k["g_late"]

        do_count[(pid, c)] += k["do1"]
        do_count[(pid, c + 1)] += k["do2"]
        do_count[(pid, c + 2)] += k["do3"]
        do_count[(pid, c + 4)] += k["do5"]

    return {
        "admission": admission, "cohorts": cohorts, "aktif": aktif,
        "lulus_ontime": lulus_ontime, "lulus_late": lulus_late, "do": do_count,
    }


# --------------------------------------------------------------------------
# 3. Tabel-tabel turunan
# --------------------------------------------------------------------------
def build_academic_tables(params, sim):
    adm, coh = sim["admission"], sim["cohorts"]
    aktif, g_on, g_late, do = sim["aktif"], sim["lulus_ontime"], sim["lulus_late"], sim["do"]

    admission_rows, retention_rows, enroll_rows = [], [], []
    grad_rows, aee_rows, tracer_rows, aktivitas_rows, demo_rows = [], [], [], [], []

    for pid, _, _ in PROGRAMS:
        p = params[pid]
        for y in REPORT_YEARS:
            a = adm[(pid, y)]
            admission_rows.append({"program_id": pid, "year": y, **a})

            k = coh[(pid, y)]
            retention_rows.append({
                "program_id": pid, "year": y,
                "year1_count": k["n1"], "year2_count": k["n2"],
                "rate": round(k["n2"] / k["n1"], 3),
            })

            n_aktif = aktif[(pid, y)]
            n_lulus = g_on[(pid, y)] + g_late[(pid, y)]
            n_do = do[(pid, y)]
            enroll_rows.append({
                "program_id": pid, "tahun": y,
                "mahasiswa_baru": a["enrolled"],
                "mahasiswa_aktif": n_aktif,
                "lulus": n_lulus,
                "do_count": n_do,
                "aee_pct": round(100 * n_lulus / (n_aktif + n_lulus), 2) if n_aktif + n_lulus else 0.0,
                "do_pct": round(100 * n_do / n_aktif, 2) if n_aktif else 0.0,
            })

            # ---- IKU 1 ----
            aee_rows.append({
                "program_id": pid, "tahun_lulus": y,
                "lulus_tepat_waktu": g_on[(pid, y)],
                "lulus_terlambat": g_late[(pid, y)],
                "lulus_total": n_lulus,
                "mahasiswa_aktif": n_aktif,
                "do_count": n_do,
                "standar_masa_studi_semester": STANDAR_MASA_STUDI_SEMESTER,
            })

            # ---- graduation (IR inti) — angkanya WAJIB sama dengan IKU 1 ----
            avg_years = (4.0 * g_on[(pid, y)] + 5.0 * g_late[(pid, y)]) / n_lulus if n_lulus else 0
            ftic = max(55, min(95, p["ftic_base"] + RNG.randint(-4, 4)))
            grad_rows.append({
                "program_id": pid, "grad_year": y,
                "grad_count": n_lulus,
                "avg_gpa": round(min(3.95, max(2.90, p["gpa_base"] + RNG.uniform(-0.12, 0.14))), 2),
                "ftic_pct": ftic, "transfer_pct": 100 - ftic,
                "avg_years": round(avg_years, 2),
            })

            # ---- IKU 2: responden <= lulusan tahun tsb ----
            resp = int(round(n_lulus * RNG.uniform(0.55, 0.92)))
            bekerja = int(round(resp * RNG.uniform(0.50, 0.70)))
            wirausaha = int(round(resp * RNG.uniform(0.04, 0.12)))
            lanjut = int(round(resp * RNG.uniform(0.05, 0.14)))
            belum = max(0, resp - bekerja - wirausaha - lanjut)
            tracer_rows.append({
                "program_id": pid, "tahun_lulus": y,
                "jumlah_lulusan": n_lulus, "jumlah_responden": resp,
                "response_rate_pct": round(100 * resp / n_lulus, 1) if n_lulus else 0.0,
                "bekerja": bekerja, "wirausaha": wirausaha, "lanjut_studi": lanjut,
                "belum_bekerja": belum,
                "waktu_tunggu_rata2_bulan": round(RNG.uniform(2.0, 7.5), 1),
            })

            # ---- IKU 3: partisipasi <= mahasiswa aktif ----
            def part(lo, hi):
                return int(round(n_aktif * RNG.uniform(lo, hi)))
            ikut_komp = part(0.05, 0.18)
            aktivitas_rows.append({
                "program_id": pid, "tahun": y,
                "mahasiswa_aktif": n_aktif,
                "ikut_kompetisi": ikut_komp,
                "menang_prestasi_nasional": int(round(ikut_komp * RNG.uniform(0.10, 0.35))),
                "menang_prestasi_internasional": int(round(ikut_komp * RNG.uniform(0.0, 0.08))),
                "ikut_pertukaran_pelajar": part(0.005, 0.03),
                "ikut_riset_dosen": part(0.03, 0.10),
                "ikut_organisasi": part(0.10, 0.28),
                "ikut_pengabdian": part(0.04, 0.15),
                "ikut_magang_bersertifikat": part(0.06, 0.20),
            })

            # ---- demographics ----
            male = RNG.randint(38, 62)
            jkt = RNG.randint(22, 40)
            jabar = RNG.randint(12, 26)
            intl = RNG.randint(2, 9)
            fee = RNG.randint(55, 78)
            demo_rows.append({
                "program_id": pid, "year": y,
                "male_pct": male, "female_pct": 100 - male,
                "region_jkt_pct": jkt, "region_jabar_pct": jabar,
                "region_other_pct": 100 - jkt - jabar - intl, "region_intl_pct": intl,
                "fee_paying_pct": fee, "assisted_pct": 100 - fee,
            })

    return {
        "admission_funnel": pd.DataFrame(admission_rows),
        "retention": pd.DataFrame(retention_rows),
        "student_enrollment": pd.DataFrame(enroll_rows),
        "graduation": pd.DataFrame(grad_rows),
        "iku1_aee": pd.DataFrame(aee_rows),
        "iku2_tracer_study": pd.DataFrame(tracer_rows),
        "iku3_aktivitas_mahasiswa": pd.DataFrame(aktivitas_rows),
        "demographics": pd.DataFrame(demo_rows),
    }


def build_lecturers():
    rows = []
    n = 0
    jabatan = ["Asisten Ahli", "Lektor", "Lektor Kepala", "Guru Besar"]
    bobot = [0.42, 0.36, 0.18, 0.04]
    for pid, _, _ in PROGRAMS:
        for _ in range(RNG.randint(6, 9)):
            n += 1
            pend = RNG.choices(["S2", "S3"], [0.72, 0.28])[0]
            jab = RNG.choices(jabatan, bobot)[0]
            if pend == "S2" and jab == "Guru Besar":
                jab = "Lektor Kepala"
            rows.append({
                "dosen_id": f"D{n:04d}", "name": f"Dosen {n:04d}", "program_id": pid,
                "jabatan_akademik": jab,
                "status_sertifikasi": RNG.choices(["Sudah", "Belum"], [0.68, 0.32])[0],
                "pendidikan_terakhir": pend,
                "tahun_mulai_kerja": RNG.randint(2004, 2023),
            })
    return pd.DataFrame(rows)


def build_lecturer_ikus(lect):
    ids = lect["dosen_id"].tolist()
    prog_of = dict(zip(lect["dosen_id"], lect["program_id"]))

    # ---- IKU 4: rekognisi dosen ----
    jenis = ["Sitasi Ilmiah Tinggi", "Penerapan Riset di Masyarakat",
             "Kepakaran Nasional", "Penghargaan Internasional"]
    tingkat = {"Sitasi Ilmiah Tinggi": "Internasional",
               "Penerapan Riset di Masyarakat": "Nasional",
               "Kepakaran Nasional": "Nasional",
               "Penghargaan Internasional": "Internasional"}
    rek = []
    for y in REPORT_YEARS:
        for _ in range(RNG.randint(8, 16)):
            d = RNG.choice(ids)
            j = RNG.choices(jenis, [0.34, 0.30, 0.24, 0.12])[0]
            rek.append({"id": len(rek) + 1, "dosen_id": d, "program_id": prog_of[d],
                        "tahun": y, "jenis_rekognisi": j, "tingkat": tingkat[j],
                        "deskripsi": f"Rekognisi {j.lower()} tahun {y}"})

    # ---- IKU 6: publikasi ----
    pub = []
    for y in REPORT_YEARS:
        for _ in range(RNG.randint(18, 32)):
            d = RNG.choice(ids)
            idx = RNG.choices(["Scopus", "WoS", "Sinta 1-2", "Lainnya"],
                              [0.40, 0.20, 0.25, 0.15])[0]
            usia = YEAR_END - y + 1
            pub.append({"id": len(pub) + 1, "dosen_id": d, "program_id": prog_of[d],
                        "tahun": y, "judul": f"Publikasi {prog_of[d]} {y}-{len(pub)+1}",
                        "indeks": idx,
                        "jumlah_sitasi": max(0, int(RNG.gauss(6 * usia, 4 * usia ** 0.5)))
                        if idx in ("Scopus", "WoS") else RNG.randint(0, 6)})

    # ---- IKU 8: SDM dalam kebijakan ----
    keterlibatan = ["Penyusunan Kebijakan", "Konsultasi Pemerintah",
                    "Konsultasi Industri", "Tenaga Ahli Lembaga"]
    instansi = ["Kemendiktisaintek", "Pemprov DKI Jakarta", "Pemkot Bekasi", "Kadin",
                "BRIN", "Bappenas", "Dinas Pendidikan Jawa Barat", "Asosiasi Industri"]
    sdm = []
    for y in REPORT_YEARS:
        for _ in range(RNG.randint(4, 9)):
            d = RNG.choice(ids)
            sdm.append({"id": len(sdm) + 1, "dosen_id": d, "program_id": prog_of[d],
                        "tahun": y, "jenis_keterlibatan": RNG.choice(keterlibatan),
                        "instansi": RNG.choice(instansi),
                        "output": RNG.choice(["Naskah akademik", "Rekomendasi kebijakan",
                                              "Policy brief", "Modul/pedoman"])})

    # ---- IKU 12: kesejahteraan dosen ----
    kesra = []
    for d in ids:
        tren = RNG.random()
        for y in REPORT_YEARS:
            maju = min(0.92, tren + 0.06 * (y - YEAR_START))
            kesra.append({
                "dosen_id": d, "program_id": prog_of[d], "tahun": y,
                "kategori_tunjangan": RNG.choices(
                    ["Fungsional", "Kinerja", "Sertifikasi Dosen", "Tidak Ada"],
                    [0.32, 0.28, 0.25, 0.15])[0],
                "ikut_pengembangan_karir": RNG.random() < maju,
                "status_perlindungan": RNG.choices(
                    ["BPJS Kesehatan & Ketenagakerjaan", "BPJS Kesehatan saja", "Tidak Ada"],
                    [maju, 1 - maju * 0.8, max(0.02, 0.20 - 0.03 * (y - YEAR_START))])[0],
                "ada_rencana_peningkatan": RNG.random() < maju,
            })

    return (pd.DataFrame(rek), pd.DataFrame(pub),
            pd.DataFrame(sdm), pd.DataFrame(kesra))


def build_institutional_ikus(aktif_per_tahun):
    # ---- IKU 5: kerja sama & hilirisasi ----
    mitra_pool = [
        ("Google Indonesia", "Industri"), ("PT Astra International", "Industri"),
        ("Tokopedia", "Industri"), ("PT Telkom Indonesia", "Industri"),
        ("Pemkot Bekasi", "Pemerintah"), ("Pemprov DKI Jakarta", "Pemerintah"),
        ("Kemendiktisaintek", "Pemerintah"), ("BRIN", "Lembaga"),
        ("LIPI Press", "Lembaga"), ("SMAN 1 Bekasi", "Sekolah"),
        ("SMKN 2 Jakarta", "Sekolah"), ("Universitas Indonesia", "Lembaga"),
        ("PT Pertamina", "Industri"), ("Bank Mandiri", "Industri"),
        ("Dinas Pendidikan Jabar", "Pemerintah"),
    ]
    ks = []
    pids = [p[0] for p in PROGRAMS]
    for i in range(52):
        nama, jenis = RNG.choice(mitra_pool)
        mulai = RNG.choice(REPORT_YEARS)
        aktif = RNG.random() < 0.65
        hilir = RNG.random() < (0.45 if jenis in ("Industri", "Pemerintah") else 0.18)
        ks.append({
            "kerjasama_id": i + 1, "nama_mitra": nama, "jenis_mitra": jenis,
            "program_terkait_id": RNG.choice(pids), "tahun_mulai": mulai,
            "tahun_berakhir": "" if aktif else min(YEAR_END, mulai + RNG.randint(1, 3)),
            "status": "Aktif" if aktif else "Selesai",
            "ada_hilirisasi": hilir,
            "jenis_luaran": RNG.choice(["Produk/Prototipe", "Lisensi/HKI", "Kebijakan mitra",
                                        "Modul pelatihan"]) if hilir else "",
            "nilai_kontrak_rupiah": RNG.randrange(25_000_000, 900_000_000, 5_000_000),
            "deskripsi_dampak": "Kolaborasi riset terapan dan magang bersertifikat"
            if hilir else "Program pengabdian dan pelatihan bersama",
        })

    # ---- IKU 7: SDGs ----
    sdgs, units = ["SDG 1", "SDG 3", "SDG 4", "SDG 8", "SDG 9", "SDG 10", "SDG 17"], \
                  ["FBE", "FST", "FOE", "FADM", "FSS", "GEN"]
    sdg_rows = []
    for y in REPORT_YEARS:
        for _ in range(RNG.randint(9, 15)):
            u = RNG.choice(units)
            sdg_rows.append({
                "kegiatan_id": len(sdg_rows) + 1,
                "judul": f"Program Pengabdian {u} {y}-{len(sdg_rows)+1}",
                "sdg_terkait": RNG.choices(sdgs, [0.16, 0.10, 0.30, 0.10, 0.08, 0.08, 0.18])[0],
                "tahun": y, "unit_pelaksana": u,
                "jumlah_penerima_manfaat": RNG.randint(45, 850),
                "sumber_dana": RNG.choice(["Internal", "Hibah Eksternal", "Mitra Industri"]),
                "anggaran_rupiah": RNG.randrange(5_000_000, 180_000_000, 1_000_000),
            })

    # ---- IKU 9: pendapatan UKT (dari jumlah mahasiswa aktif) + non-UKT ----
    # UKT ditarik dari headcount supaya trennya sinkron dengan student_enrollment,
    # lalu total non-UKT ditetapkan dari porsi target yang naik bertahap.
    TARIF_UKT_2021 = 32_000_000     # rata-rata per mahasiswa per tahun
    sumber = ["Bisnis Kampus", "Pelatihan & Sertifikasi", "Konsultasi",
              "Hibah Penelitian", "Kerjasama Industri", "Unit Usaha Kampus"]
    bobot_sumber = [0.24, 0.18, 0.10, 0.20, 0.20, 0.08]

    non_ukt, ukt = [], []
    for y in REPORT_YEARS:
        i = y - YEAR_START
        tarif = TARIF_UKT_2021 * (1.04 ** i)                    # kenaikan tarif ~4%/th
        ukt_val = int(round(aktif_per_tahun[y] * tarif / 1_000_000) * 1_000_000)
        share = 0.12 + 0.018 * i                                # porsi non-UKT: 12% -> 21%
        target_non_ukt = ukt_val * share / (1 - share)

        tot = 0
        for s, b in zip(sumber, bobot_sumber):
            val = int(round(target_non_ukt * b * RNG.uniform(0.85, 1.15) / 1_000_000) * 1_000_000)
            non_ukt.append({"id": len(non_ukt) + 1, "tahun": y, "sumber": s,
                            "jumlah_rupiah": val})
            tot += val

        ukt.append({
            "tahun": y,
            "mahasiswa_aktif": aktif_per_tahun[y],
            "tarif_ukt_rata2_rupiah": int(round(tarif / 1_000_000) * 1_000_000),
            "pendapatan_ukt_rupiah": ukt_val,
            "pendapatan_non_ukt_rupiah": tot,
            "total_pendapatan_rupiah": ukt_val + tot,
            "porsi_non_ukt_pct": round(100 * tot / (ukt_val + tot), 2),
        })

    # ---- IKU 11: tata kelola, 6 komponen sesuai Kepmen ----
    kategori = ["Audit Keuangan", "SAKIP", "Integritas Akademik",
                "Pencegahan Kekerasan (PPKS)", "Anti Narkoba", "Anti Korupsi"]
    skala = ["Kurang", "Cukup", "Baik", "Sangat Baik"]
    tk = []
    for kat in kategori:
        lvl = RNG.randint(1, 2)  # mulai dari Cukup/Baik
        for y in REPORT_YEARS:
            if RNG.random() < 0.35:
                lvl = min(3, lvl + 1)
            tk.append({
                "id": len(tk) + 1, "tahun": y, "kategori": kat,
                "skor_atau_status": skala[lvl],
                "skor_numerik": {0: 55, 1: 70, 2: 82, 3: 92}[lvl] + RNG.randint(-3, 3),
                "ada_dokumen_bukti": RNG.random() < 0.8,
            })

    return (pd.DataFrame(ks), pd.DataFrame(sdg_rows), pd.DataFrame(non_ukt),
            pd.DataFrame(ukt), pd.DataFrame(tk))


def build_iku_target():
    """Metadata + target per IKU per tahun. Status mengacu Kepmendiktisaintek
    358/M/KEP/2026 dengan sudut pandang PTS."""
    meta = [
        (1, "AEE PT", "Wajib", "iku1_aee + student_enrollment",
         "lulus_total / (mahasiswa_aktif + lulus_total) x 100", "%", 18.0, 1.2),
        (2, "Lulusan Terserap", "Wajib", "iku2_tracer_study",
         "(bekerja+wirausaha+lanjut_studi) / jumlah_responden x 100", "%", 78.0, 2.0),
        (3, "Aktivitas & Prestasi Mahasiswa", "Wajib", "iku3_aktivitas_mahasiswa",
         "mahasiswa dengan >=1 aktivitas / mahasiswa_aktif x 100", "%", 25.0, 3.0),
        (4, "Rekognisi Dosen", "Pilihan", "iku4_rekognisi_dosen",
         "dosen dengan >=1 rekognisi / total dosen x 100", "%", 15.0, 2.5),
        (5, "Kerja Sama & Hilirisasi", "Wajib", "iku5_kerjasama",
         "kerja sama aktif dengan hilirisasi / kerja sama aktif x 100", "%", 30.0, 3.0),
        (6, "Publikasi Internasional", "Pilihan", "iku6_publikasi",
         "publikasi Scopus/WoS per tahun", "dokumen", 20.0, 3.0),
        (7, "Kontribusi SDGs", "Wajib", "iku7_sdgs",
         "jumlah kegiatan ber-SDG per tahun", "kegiatan", 10.0, 1.5),
        (8, "SDM dalam Kebijakan", "Pilihan", "iku8_sdm_kebijakan",
         "jumlah keterlibatan kebijakan per tahun", "kegiatan", 5.0, 1.0),
        (9, "Pendapatan Non-UKT", "Wajib", "iku9_pendapatan_non_ukt + iku9_pendapatan_ukt",
         "pendapatan_non_ukt / total_pendapatan x 100", "%", 17.0, 2.0),
        (10, "Zona Integritas (WBK/WBBM)", "Tidak Berlaku (PTS)", "-",
         "-", "-", None, None),
        (11, "Tata Kelola Berintegritas", "Pilihan", "iku11_tata_kelola",
         "rata-rata skor_numerik 6 komponen", "skor", 75.0, 3.0),
        (12, "Kesejahteraan Dosen", "Wajib", "iku12_kesejahteraan_dosen",
         "dosen dengan perlindungan penuh / total dosen x 100", "%", 60.0, 5.0),
    ]
    rows = []
    for no, nama, status, tabel, formula, satuan, t0, step in meta:
        for i, y in enumerate(REPORT_YEARS):
            rows.append({
                "iku_no": no, "nama_iku": nama, "status_pts": status,
                "tabel_sumber": tabel, "formula": formula, "satuan": satuan,
                "tahun": y,
                "target": round(t0 + step * i, 1) if t0 is not None else "",
                "keterangan": "Khusus PTN/instansi pemerintah, tidak dinilai untuk PTS"
                if no == 10 else "",
            })
    return pd.DataFrame(rows)


def build_dashboard_users():
    rows = [{"username": "rektor", "role": "rektor", "faculty_id": "",
             "program_id": "", "bureau": ""}]
    for fid, _, short in FACULTIES:
        rows.append({"username": f"dekan_{short.lower()}", "role": "dekan",
                     "faculty_id": fid, "program_id": "", "bureau": ""})
    for pid, _, fid in PROGRAMS:
        rows.append({"username": f"kaprodi_{pid.lower()}", "role": "kaprodi",
                     "faculty_id": fid, "program_id": pid, "bureau": ""})
    for b in ("akademik", "admisi", "keuangan", "sdm"):
        rows.append({"username": f"kabag_{b}", "role": "kabag", "faculty_id": "",
                     "program_id": "", "bureau": b})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 4. Validasi — gagal keras kalau dataset tidak konsisten
# --------------------------------------------------------------------------
def validate(t):
    errs = []

    g = t["graduation"].merge(t["iku1_aee"], left_on=["program_id", "grad_year"],
                              right_on=["program_id", "tahun_lulus"])
    if (g["grad_count"] != g["lulus_total"]).any():
        errs.append("graduation.grad_count != iku1_aee.lulus_total")

    r = t["retention"].merge(t["admission_funnel"], on=["program_id", "year"])
    if (r["year1_count"] != r["enrolled"]).any():
        errs.append("retention.year1_count != admission_funnel.enrolled")

    a = t["iku1_aee"]
    if (a["lulus_total"] != a["lulus_tepat_waktu"] + a["lulus_terlambat"]).any():
        errs.append("lulus_total != tepat_waktu + terlambat")

    e = t["student_enrollment"].sort_values(["program_id", "tahun"])
    for pid, grp in e.groupby("program_id"):
        grp = grp.reset_index(drop=True)
        for i in range(1, len(grp)):
            prev, cur = grp.loc[i - 1], grp.loc[i]
            expected = prev.mahasiswa_aktif + cur.mahasiswa_baru - prev.lulus - prev.do_count
            if expected != cur.mahasiswa_aktif:
                errs.append(f"neraca mahasiswa {pid} {cur.tahun}: "
                            f"harap {expected}, dapat {cur.mahasiswa_aktif}")

    tr = t["iku2_tracer_study"]
    if (tr["jumlah_responden"] > tr["jumlah_lulusan"]).any():
        errs.append("responden tracer > jumlah lulusan")
    if (tr[["bekerja", "wirausaha", "lanjut_studi", "belum_bekerja"]].sum(axis=1)
            != tr["jumlah_responden"]).any():
        errs.append("komponen tracer tidak menjumlah ke responden")

    ak = t["iku3_aktivitas_mahasiswa"]
    for c in ["ikut_kompetisi", "ikut_organisasi", "ikut_pengabdian", "ikut_riset_dosen"]:
        if (ak[c] > ak["mahasiswa_aktif"]).any():
            errs.append(f"{c} > mahasiswa_aktif")

    u = t["iku9_pendapatan_ukt"]
    agg = t["iku9_pendapatan_non_ukt"].groupby("tahun")["jumlah_rupiah"].sum()
    if (u.set_index("tahun")["pendapatan_non_ukt_rupiah"] != agg).any():
        errs.append("total non-UKT di iku9_pendapatan_ukt != agregat iku9_pendapatan_non_ukt")
    ea = t["student_enrollment"].groupby("tahun")["mahasiswa_aktif"].sum()
    if (u.set_index("tahun")["mahasiswa_aktif"] != ea).any():
        errs.append("mahasiswa_aktif di IKU 9 != agregat student_enrollment")

    if t["iku12_kesejahteraan_dosen"]["dosen_id"].nunique() != len(t["lecturers"]):
        errs.append("jumlah dosen di IKU 12 != tabel lecturers")

    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./csv")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    params = build_program_params()
    sim = simulate(params)
    tables = build_academic_tables(params, sim)

    tables["faculties"] = pd.DataFrame(FACULTIES, columns=["faculty_id", "name", "short_name"])
    tables["programs"] = pd.DataFrame(
        [(p, n, f, "S1") for p, n, f in PROGRAMS],
        columns=["program_id", "name", "faculty_id", "jenjang"])
    tables["lecturers"] = build_lecturers()
    tables["dashboard_users"] = build_dashboard_users()

    rek, pub, sdm, kesra = build_lecturer_ikus(tables["lecturers"])
    tables["iku4_rekognisi_dosen"] = rek
    tables["iku6_publikasi"] = pub
    tables["iku8_sdm_kebijakan"] = sdm
    tables["iku12_kesejahteraan_dosen"] = kesra

    aktif_per_tahun = (tables["student_enrollment"]
                       .groupby("tahun")["mahasiswa_aktif"].sum().to_dict())
    ks, sdg, non_ukt, ukt, tk = build_institutional_ikus(aktif_per_tahun)
    tables["iku5_kerjasama"] = ks
    tables["iku7_sdgs"] = sdg
    tables["iku9_pendapatan_non_ukt"] = non_ukt
    tables["iku9_pendapatan_ukt"] = ukt
    tables["iku11_tata_kelola"] = tk
    tables["iku_target"] = build_iku_target()

    errs = validate(tables)
    if errs:
        print("VALIDASI GAGAL:")
        for e in errs[:20]:
            print("  -", e)
        raise SystemExit(1)

    for name, df in sorted(tables.items()):
        path = os.path.join(args.out, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"{name:32s} {len(df):5d} baris  ->  {path}")
    print(f"\n{len(tables)} tabel. Semua uji konsistensi lolos.")


if __name__ == "__main__":
    main()
