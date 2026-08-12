# Blueprint: Dashboard IR + 12 IKU Kemdiktisaintek dari Nol
**Studi kasus: Sampoerna University · Superset (self-hosted) · Kepmendiktisaintek No. 358/M/KEP/2025**

> **Versi 2 — 10 Agustus 2026.** Ringkasan perubahan dari v1 ada di Bagian 8.
> Perubahan terbesar: dataset dummy kini diturunkan dari **satu simulasi kohor**,
> bukan random per tabel. Di v1, `graduation.grad_count` berbeda dari
> `iku1_aee.lulus_total` pada 67 dari 72 baris dan `retention.year1_count`
> berbeda dari `admission_funnel.enrolled` pada 72 dari 72 baris — artinya
> "jumlah lulusan" akan menunjukkan angka berbeda tergantung chart mana yang
> dibuka. Untuk dashboard eksekutif, itu masalah kredibilitas, bukan sekadar
> kosmetik.

**Catatan nomor regulasi.** Yang benar adalah **358/M/KEP/2025** — ditetapkan
2025, berlaku mulai penilaian 2026. Beberapa artikel populer menulis
"358/M/KEP/2026"; itu keliru. Rujuk selalu salinan resmi dari LLDikti wilayah
masing-masing.

File pendamping blueprint ini:
- `schema.sql` — struktur database lengkap (22 tabel + 6 view indikator)
- `generate_dataset.py` — generator data dummy konsisten + uji validasi bawaan
- `csv/` — 22 file CSV hasil generator, siap di-import
- `docker-compose.yml` — deployment Superset + PostgreSQL

---

## 1. Arsitektur Sistem

```
                    ┌───────────────────────┐
   Rektor/Dekan/    │   Apache Superset     │
   Kaprodi/Kabag ──▶│   (Docker container)  │
   (browser)        │   + Row-Level Security│
                    └──────────┬────────────┘
                               │ SQL query (via VIEW, bukan tabel mentah)
                    ┌──────────▼────────────┐
                    │   PostgreSQL           │
                    │   db: dashboard_iku    │
                    │   22 tabel + 6 view    │
                    └──────────▲─────────────┘
                               │ CSV import (tahap awal)
                               │ / integrasi sistem asli (tahap lanjut)
                    ┌──────────┴─────────────┐
                    │  Sumber data nyata:     │
                    │  SIAKAD, HRIS,          │
                    │  Finance system, SINTA  │
                    └─────────────────────────┘
```

Tahap awal: data dummy → CSV → PostgreSQL → Superset.
Tahap produksi: ganti sumber CSV dengan koneksi langsung ke sistem asli — struktur
tabel & dashboard **tidak perlu diubah**, cukup ganti query/ETL sumbernya.

**Satu aturan yang menghemat banyak waktu di fase 4:** dataset Superset menunjuk ke
**view** (`v_iku1_aee`, `v_iku2_terserap`, dst), bukan ke tabel mentah. Definisi
indikator dengan begitu hanya hidup di satu tempat. Kalau nanti Kemdiktisaintek
merevisi rumus AEE, Anda mengubah satu view, bukan belasan chart.

---

## 2. Struktur Database (22 tabel)

| Kelompok | Tabel | Isi |
|---|---|---|
| Referensi (4) | `faculties`, `programs`, `lecturers`, `dashboard_users` | Data master + peta RBAC |
| IR Inti (5) | `admission_funnel`, `retention`, **`student_enrollment`**, `graduation`, `demographics` | `student_enrollment` **baru** — lihat di bawah |
| IKU Wajib (7) | `iku1_aee`, `iku2_tracer_study`, `iku3_aktivitas_mahasiswa`, `iku5_kerjasama`, `iku7_sdgs`, `iku9_pendapatan_non_ukt` + **`iku9_pendapatan_ukt`**, `iku12_kesejahteraan_dosen` | 8 tabel untuk 7 IKU |
| IKU Pilihan (4) | `iku4_rekognisi_dosen`, `iku6_publikasi`, `iku8_sdm_kebijakan`, `iku11_tata_kelola` | Fase lanjutan |
| Metadata (1) | **`iku_target`** | Target, satuan, rumus, status wajib/pilihan per IKU per tahun |

**`student_enrollment` adalah tabel paling penting yang tidak ada di v1.** Tanpa
jumlah mahasiswa aktif, IKU 1 tidak bisa dihitung sesuai definisinya (AEE butuh
penyebut) dan IKU 3 hanya bisa ditampilkan sebagai angka absolut — 20 peserta
kompetisi di prodi 60 mahasiswa dan di prodi 400 mahasiswa akan terlihat sama.
Tabel ini juga membawa `do_count`, padahal penurunan DO justru fokus utama IKU 1.

Neraca yang dijaga generator dan wajib tetap berlaku saat migrasi ke data asli:

```
mahasiswa_aktif(t+1) = mahasiswa_aktif(t) + mahasiswa_baru(t+1)
                       − lulus(t) − do_count(t)
```

---

## 3. Pemetaan 12 IKU → Tabel → Rumus → Chart

| IKU | Sifat (PTS) | Tabel / View | Rumus | Chart | Tipe Superset |
|---|---|---|---|---|---|
| 1. AEE PT | Wajib | `v_iku1_aee` | `lulus_total / (mahasiswa_aktif + lulus_total) × 100` | AEE & % tepat waktu per prodi, tren DO | Bar + Big Number w/ trendline |
| 2. Lulusan Terserap | Wajib | `v_iku2_terserap` | `(bekerja+wirausaha+lanjut_studi) / responden × 100` | Komposisi + response rate | Stacked bar |
| 3. Aktivitas Mahasiswa | Wajib | `v_iku3_aktivitas` | `partisipasi / mahasiswa_aktif × 100` | Tren partisipasi per kategori | Line multi-series |
| 4. Rekognisi Dosen | Pilihan | `iku4_rekognisi_dosen` | `dosen ber-rekognisi / total dosen × 100` | Per jenis & tingkat | Bar + Big Number |
| 5. Kerja Sama & Hilirisasi | Wajib | `v_iku5_hilirisasi` | `kerjasama_hilirisasi / kerjasama_aktif × 100` | Mitra aktif per jenis, % hilirisasi | Bar + Big Number (%) |
| 6. Publikasi Internasional | Pilihan* | `iku6_publikasi` | jumlah dokumen Scopus/WoS per tahun | Tren + sitasi per prodi | Line + Table |
| 7. Kontribusi SDGs | Wajib | `iku7_sdgs` | jumlah kegiatan & penerima manfaat per SDG | Per SDG | Bar horizontal / Treemap |
| 8. SDM dalam Kebijakan | Pilihan | `iku8_sdm_kebijakan` | jumlah keterlibatan per tahun | Per instansi & jenis | Bar |
| 9. Pendapatan Non-UKT | Wajib | `v_iku9_non_ukt` | `non_ukt / total_pendapatan × 100` | Tren per sumber + porsi | Stacked area + Big Number |
| 10. Zona Integritas | **Tidak berlaku** | — | — | — | — |
| 11. Tata Kelola Berintegritas | Pilihan | `iku11_tata_kelola` | rata-rata skor 6 komponen | Heatmap komponen × tahun | Heatmap |
| 12. Kesejahteraan Dosen | Wajib | `v_iku12_kesejahteraan` | `perlindungan penuh / total dosen × 100` | % perlindungan & pengembangan karier | Big Number + Bar |

\* IKU 6 wajib bagi PTN Badan Hukum; pilihan bagi PTN non-BH dan PTS.

Chart Funnel (admisi) dan Heatmap (retensi program × tahun) tetap dipakai untuk
modul IR inti — keduanya didukung native oleh Superset.

**IKU 11 punya 6 komponen, bukan 4.** Versi v1 hanya memuat Audit Keuangan, SAKIP,
Integritas Akademik, dan Anti Korupsi. Dua yang hilang — **Pencegahan Kekerasan
(PPKS)** dan **Anti Narkoba** — sudah ditambahkan, keduanya punya kewajiban
pelaporan tersendiri sehingga tidak bisa dilewat.

---

## 4. Desain RBAC (Row-Level Security)

Tabel `dashboard_users` memetakan setiap akun ke cakupan datanya:

| Role | Scope | Rule RLS |
|---|---|---|
| Rektor | Semua fakultas & prodi | Tidak ada filter |
| Dekan | 1 fakultas | `faculty_id = '<fakultas user>'` |
| Kaprodi | 1 prodi | `program_id = '<prodi user>'` |
| Kabag | Per bureau (akademik/admisi/keuangan/sdm) | Akses hanya ke dataset domainnya |

Konfigurasi: **Settings → Row Level Security → Add Rule**, pilih dataset target,
isi filter clause berbasis kolom `faculty_id`/`program_id`, kaitkan ke role Superset.

Tiga hal yang perlu diputuskan di depan, bukan ditemukan saat testing:

1. **RLS bekerja per dataset.** Rule harus diulang untuk setiap dataset relevan.
   Dengan ~15 dataset × 4 role, ini puluhan rule — buat penamaan yang konsisten
   (`rls_<dataset>_<role>`) sejak awal.
2. **Semua view sudah membawa `faculty_id`.** Ini sengaja: tanpa kolom itu di
   level baris, rule dekan tidak bisa ditulis dan Anda terpaksa membuat dataset
   terpisah per fakultas.
3. **IKU 7, 9, dan 11 bersifat institusional**, tidak punya dimensi prodi. IKU 7
   masih bisa difilter lewat `unit_pelaksana`, tapi IKU 9 dan 11 tidak. Pilihan:
   (a) sembunyikan tab-nya dari role dekan/kaprodi, atau (b) tampilkan sebagai
   konteks read-only dengan label jelas "angka tingkat institusi". Rekomendasi:
   opsi (a) untuk IKU 9 (angka keuangan), opsi (b) untuk IKU 11.

---

## 5. Roadmap Eksekusi

### Fase 0 — Infrastruktur (1–2 hari)
1. `docker compose up -d` (otomatis load `schema.sql`)
2. `python3 generate_dataset.py --out ./csv` — skrip berhenti dengan exit code 1
   bila ada uji konsistensi yang gagal, jadi CSV yang keluar dijamin lolos validasi
3. Import CSV ke tiap tabel (`psql \copy` lebih andal daripada Superset "Upload CSV"
   untuk tabel ber-foreign key; urutkan: referensi → IR inti → IKU)
4. Tambahkan koneksi database di Superset, buat Dataset **per view**, bukan per tabel

### Fase 1 — Modul IR Inti + RBAC (1 minggu)
5. Bangun chart dari mockup: KPI cards, funnel admisi, tren retensi, distribusi fakultas
6. Aktifkan Row-Level Security sesuai Bagian 4, uji dengan akun dummy tiap role

### Fase 2 — 7 IKU Wajib (2–3 minggu)
7. Satu dashboard "IKU Wajib" berisi 7 section, plus scorecard capaian-vs-target
   yang menarik angka dari `iku_target`
8. Validasi tiap angka dengan definisi resmi Kepmen (terutama standar masa studi
   IKU 1, kategori sumber IKU 9, cakupan "terserap" IKU 2)

### Fase 3 — 4 IKU Pilihan (opsional)
9. Tambahkan Rekognisi Dosen, Publikasi (bisa terhubung nyata ke SINTA),
   SDM dalam Kebijakan, Tata Kelola

### Fase 4 — Migrasi ke data nyata
10. Ganti sumber per tabel: SIAKAD/PDDIKTI (akademik + `student_enrollment`),
    sistem keuangan (IKU 9, termasuk `iku9_pendapatan_ukt`), HRIS (IKU 12/4/8),
    SINTA API (IKU 6), unit SPI/LPM (IKU 11)
11. **Jalankan ulang fungsi `validate()` dari `generate_dataset.py` terhadap data
    asli.** Ini bagian yang paling sering dilewat: data produksi dari sistem yang
    berbeda hampir selalu melanggar neraca mahasiswa di awal, dan lebih baik
    ketahuan lewat assert daripada lewat pertanyaan Rektor di rapat
12. Uji ulang seluruh RLS dan validasi angka dengan unit terkait (BAAK, Keuangan,
    SDM, LPPM)

---

## 6. Uji Konsistensi yang Dijalankan Generator

`generate_dataset.py` gagal keras kalau salah satu tidak terpenuhi:

| # | Uji | Alasan |
|---|---|---|
| 1 | `graduation.grad_count = iku1_aee.lulus_total` | Jumlah lulusan harus sama di semua chart |
| 2 | `retention.year1_count = admission_funnel.enrolled` | Kohor tahun 1 = mahasiswa yang daftar ulang |
| 3 | `lulus_total = lulus_tepat_waktu + lulus_terlambat` | Identitas IKU 1 |
| 4 | Neraca mahasiswa antar tahun (lihat Bagian 2) | Mencegah mahasiswa aktif "muncul dari langit" |
| 5 | `jumlah_responden ≤ jumlah_lulusan` | Response rate tidak boleh > 100% |
| 6 | Komponen tracer menjumlah tepat ke responden | IKU 2 |
| 7 | Angka partisipasi ≤ `mahasiswa_aktif` | IKU 3 |
| 8 | Agregat IKU 9 non-UKT = total di `iku9_pendapatan_ukt` | IKU 9 |
| 9 | `mahasiswa_aktif` di IKU 9 = agregat `student_enrollment` | Tarif UKT diturunkan dari headcount |
| 10 | Jumlah dosen di IKU 12 = jumlah baris `lecturers` | Cakupan 100% dosen |

Jadikan uji 1–10 sebagai **regression test ETL** di fase 4.

---

## 7. Catatan Penting

- **IKU 10 (Zona Integritas) sengaja tidak dibuat sebagai tabel** — WBK/WBBM khusus
  PTN/instansi pemerintah, tidak berlaku untuk PTS seperti Sampoerna University.
  Statusnya tetap tercatat di `iku_target` dengan `status_pts = 'Tidak Berlaku (PTS)'`
  supaya 12 IKU tetap terdokumentasi utuh dan tidak terlihat seperti kelalaian
  saat diaudit.
- **IKU 6 (Publikasi Internasional)** satu-satunya modul dengan sumber data publik
  nyata (SINTA) — pertimbangkan sambungkan lebih awal daripada modul lain.
- **`iku_target` adalah pembeda antara dashboard monitoring dan dashboard laporan.**
  Tanpa tabel target, dashboard hanya bisa menjawab "berapa angkanya", bukan
  "apakah kita on-track". Angka target di dataset dummy adalah placeholder —
  ganti dengan target dari Renstra/kontrak kinerja institusi.
- Semua data di `generate_dataset.py` sepenuhnya sintetis (`SEED = 20260810`,
  reproducible) — aman untuk demo/latihan, tidak merepresentasikan data mahasiswa
  atau dosen sungguhan.
- Angka dummy dikalibrasi ke rentang yang masuk akal (AEE 13–19%, DO 5–9%,
  porsi non-UKT 12→20%, retensi 80–93%) supaya chart terlihat wajar saat demo,
  **bukan** karena mencerminkan kondisi Sampoerna University sebenarnya.
- Sebelum dashboard dipakai untuk laporan resmi ke Kemdiktisaintek, **definisi
  setiap indikator wajib divalidasi ulang** dengan teks lengkap Kepmendiktisaintek
  No. 358/M/KEP/2025 (khususnya ambang batas per IKU). Blueprint ini kerangka
  teknis, bukan pengganti kepatuhan regulasi.

---

## 8. Ringkasan Perubahan v1 → v2

| Area | v1 | v2 |
|---|---|---|
| Jumlah tabel | 18 (klaim) / 19 (aktual) | 22, terverifikasi |
| Konsistensi data | Tiap tabel di-generate acak & independen | Satu simulasi kohor + 10 uji validasi |
| IKU 1 | Tanpa penyebut, tanpa data DO | `student_enrollment` + kolom DO, AEE dapat dihitung |
| IKU 3 | Hanya angka absolut | Ada `mahasiswa_aktif` sebagai penyebut; prestasi dipisah nasional/internasional |
| IKU 9 | Hanya pendapatan non-UKT | + `iku9_pendapatan_ukt` sebagai pembanding, porsi non-UKT terhitung |
| IKU 11 | 4 komponen | 6 komponen (+ PPKS, Anti Narkoba) + skor numerik |
| IKU 2 | Responden lepas dari lulusan | Responden terikat jumlah lulusan + `response_rate_pct` |
| IKU 5 | Tanpa nilai/luaran | + `jenis_luaran`, `nilai_kontrak_rupiah` |
| Target | Tidak ada | `iku_target`: target, rumus, satuan, status wajib/pilihan |
| Lapisan semantik | Chart langsung ke tabel | 6 view indikator, satu sumber definisi |
| RLS | Disebut sekilas | Tiga keputusan desain eksplisit, termasuk penanganan tabel institusional |
