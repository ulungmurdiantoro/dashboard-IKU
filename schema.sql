-- =====================================================================
-- schema.sql — Dashboard IR + 12 IKU Kemdiktisaintek
-- Target: PostgreSQL 14+  ·  database: dashboard_iku
-- 22 tabel: 4 referensi, 5 IR inti, 12 IKU (11 tabel + 1 pembanding), 1 metadata
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- A. TABEL REFERENSI
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS faculties (
    faculty_id   VARCHAR(10) PRIMARY KEY,
    name         VARCHAR(150) NOT NULL,
    short_name   VARCHAR(20)  NOT NULL
);

CREATE TABLE IF NOT EXISTS programs (
    program_id   VARCHAR(10) PRIMARY KEY,
    name         VARCHAR(150) NOT NULL,
    faculty_id   VARCHAR(10)  NOT NULL REFERENCES faculties(faculty_id),
    jenjang      VARCHAR(10)  NOT NULL DEFAULT 'S1'
);

CREATE TABLE IF NOT EXISTS lecturers (
    dosen_id             VARCHAR(10) PRIMARY KEY,
    name                 VARCHAR(150) NOT NULL,
    program_id           VARCHAR(10)  NOT NULL REFERENCES programs(program_id),
    jabatan_akademik     VARCHAR(50),
    status_sertifikasi   VARCHAR(20),
    pendidikan_terakhir  VARCHAR(10),
    tahun_mulai_kerja    SMALLINT
);

-- Peta akun -> cakupan data, dipakai sebagai dasar Row-Level Security.
CREATE TABLE IF NOT EXISTS dashboard_users (
    username     VARCHAR(50) PRIMARY KEY,
    role         VARCHAR(20) NOT NULL
                 CHECK (role IN ('rektor','dekan','kaprodi','kabag')),
    faculty_id   VARCHAR(10) REFERENCES faculties(faculty_id),
    program_id   VARCHAR(10) REFERENCES programs(program_id),
    bureau       VARCHAR(30)
);

-- ---------------------------------------------------------------------
-- B. IR INTI
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admission_funnel (
    program_id  VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    year        SMALLINT    NOT NULL,
    complete    INTEGER     NOT NULL CHECK (complete >= 0),
    admitted    INTEGER     NOT NULL CHECK (admitted >= 0),
    enrolled    INTEGER     NOT NULL CHECK (enrolled >= 0),
    PRIMARY KEY (program_id, year),
    CHECK (admitted <= complete),
    CHECK (enrolled <= admitted)
);

CREATE TABLE IF NOT EXISTS retention (
    program_id   VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    year         SMALLINT    NOT NULL,
    year1_count  INTEGER     NOT NULL,
    year2_count  INTEGER     NOT NULL,
    rate         NUMERIC(4,3) NOT NULL,
    PRIMARY KEY (program_id, year),
    CHECK (year2_count <= year1_count)
);

-- BARU. Penyebut AEE (IKU 1) dan basis persentase partisipasi (IKU 3).
-- Neraca yang harus selalu berlaku:
--   mahasiswa_aktif(t+1) = mahasiswa_aktif(t) + mahasiswa_baru(t+1)
--                          - lulus(t) - do_count(t)
CREATE TABLE IF NOT EXISTS student_enrollment (
    program_id       VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    tahun            SMALLINT    NOT NULL,
    mahasiswa_baru   INTEGER     NOT NULL CHECK (mahasiswa_baru   >= 0),
    mahasiswa_aktif  INTEGER     NOT NULL CHECK (mahasiswa_aktif  >= 0),
    lulus            INTEGER     NOT NULL CHECK (lulus            >= 0),
    do_count         INTEGER     NOT NULL CHECK (do_count         >= 0),
    aee_pct          NUMERIC(5,2),   -- kolom turunan, disimpan untuk kemudahan chart
    do_pct           NUMERIC(5,2),
    PRIMARY KEY (program_id, tahun)
);

CREATE TABLE IF NOT EXISTS graduation (
    program_id    VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    grad_year     SMALLINT    NOT NULL,
    grad_count    INTEGER     NOT NULL,
    avg_gpa       NUMERIC(3,2),
    ftic_pct      SMALLINT,
    transfer_pct  SMALLINT,
    avg_years     NUMERIC(4,2),
    PRIMARY KEY (program_id, grad_year)
);

CREATE TABLE IF NOT EXISTS demographics (
    program_id        VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    year              SMALLINT    NOT NULL,
    male_pct          SMALLINT, female_pct       SMALLINT,
    region_jkt_pct    SMALLINT, region_jabar_pct SMALLINT,
    region_other_pct  SMALLINT, region_intl_pct  SMALLINT,
    fee_paying_pct    SMALLINT, assisted_pct     SMALLINT,
    PRIMARY KEY (program_id, year)
);

-- ---------------------------------------------------------------------
-- C. IKU WAJIB
-- ---------------------------------------------------------------------

-- IKU 1 — AEE PT
CREATE TABLE IF NOT EXISTS iku1_aee (
    program_id                   VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    tahun_lulus                  SMALLINT    NOT NULL,
    lulus_tepat_waktu            INTEGER     NOT NULL,
    lulus_terlambat              INTEGER     NOT NULL,
    lulus_total                  INTEGER     NOT NULL,
    mahasiswa_aktif              INTEGER     NOT NULL,
    do_count                     INTEGER     NOT NULL,
    standar_masa_studi_semester  SMALLINT    NOT NULL DEFAULT 8,
    PRIMARY KEY (program_id, tahun_lulus),
    CHECK (lulus_total = lulus_tepat_waktu + lulus_terlambat)
);

-- IKU 2 — Lulusan terserap (maks 1 tahun setelah lulus)
CREATE TABLE IF NOT EXISTS iku2_tracer_study (
    program_id                VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    tahun_lulus               SMALLINT    NOT NULL,
    jumlah_lulusan            INTEGER     NOT NULL,
    jumlah_responden          INTEGER     NOT NULL,
    response_rate_pct         NUMERIC(5,1),
    bekerja                   INTEGER     NOT NULL,
    wirausaha                 INTEGER     NOT NULL,
    lanjut_studi              INTEGER     NOT NULL,
    belum_bekerja             INTEGER     NOT NULL,
    waktu_tunggu_rata2_bulan  NUMERIC(4,1),
    PRIMARY KEY (program_id, tahun_lulus),
    CHECK (jumlah_responden <= jumlah_lulusan),
    CHECK (bekerja + wirausaha + lanjut_studi + belum_bekerja = jumlah_responden)
);

-- IKU 3 — Aktivitas & prestasi mahasiswa
CREATE TABLE IF NOT EXISTS iku3_aktivitas_mahasiswa (
    program_id                     VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    tahun                          SMALLINT    NOT NULL,
    mahasiswa_aktif                INTEGER     NOT NULL,
    ikut_kompetisi                 INTEGER     NOT NULL,
    menang_prestasi_nasional       INTEGER     NOT NULL,
    menang_prestasi_internasional  INTEGER     NOT NULL,
    ikut_pertukaran_pelajar        INTEGER     NOT NULL,
    ikut_riset_dosen               INTEGER     NOT NULL,
    ikut_organisasi                INTEGER     NOT NULL,
    ikut_pengabdian                INTEGER     NOT NULL,
    ikut_magang_bersertifikat      INTEGER     NOT NULL,
    PRIMARY KEY (program_id, tahun)
);

-- IKU 5 — Kerja sama & hilirisasi
CREATE TABLE IF NOT EXISTS iku5_kerjasama (
    kerjasama_id          SERIAL PRIMARY KEY,
    nama_mitra            VARCHAR(150) NOT NULL,
    jenis_mitra           VARCHAR(30)
                          CHECK (jenis_mitra IN ('Industri','Pemerintah','Sekolah','Lembaga')),
    program_terkait_id    VARCHAR(10) REFERENCES programs(program_id),
    tahun_mulai           SMALLINT,
    tahun_berakhir        SMALLINT,
    status                VARCHAR(20) CHECK (status IN ('Aktif','Selesai')),
    ada_hilirisasi        BOOLEAN NOT NULL DEFAULT FALSE,
    jenis_luaran          VARCHAR(50),
    nilai_kontrak_rupiah  BIGINT,
    deskripsi_dampak      TEXT
);

-- IKU 7 — Kontribusi SDGs
CREATE TABLE IF NOT EXISTS iku7_sdgs (
    kegiatan_id              SERIAL PRIMARY KEY,
    judul                    VARCHAR(200) NOT NULL,
    sdg_terkait              VARCHAR(10)  NOT NULL,
    tahun                    SMALLINT     NOT NULL,
    unit_pelaksana           VARCHAR(10)  NOT NULL,  -- faculty_id atau 'GEN'
    jumlah_penerima_manfaat  INTEGER,
    sumber_dana              VARCHAR(30),
    anggaran_rupiah          BIGINT
);

-- IKU 9 — Pendapatan non-UKT (rincian per sumber)
CREATE TABLE IF NOT EXISTS iku9_pendapatan_non_ukt (
    id             SERIAL PRIMARY KEY,
    tahun          SMALLINT     NOT NULL,
    sumber         VARCHAR(50)  NOT NULL,
    jumlah_rupiah  BIGINT       NOT NULL
);

-- IKU 9 — pembanding: pendapatan UKT & total (penyebut rasio non-UKT)
CREATE TABLE IF NOT EXISTS iku9_pendapatan_ukt (
    tahun                      SMALLINT PRIMARY KEY,
    mahasiswa_aktif            INTEGER,
    tarif_ukt_rata2_rupiah     BIGINT,
    pendapatan_ukt_rupiah      BIGINT NOT NULL,
    pendapatan_non_ukt_rupiah  BIGINT NOT NULL,
    total_pendapatan_rupiah    BIGINT NOT NULL,
    porsi_non_ukt_pct          NUMERIC(5,2),
    CHECK (total_pendapatan_rupiah = pendapatan_ukt_rupiah + pendapatan_non_ukt_rupiah)
);

-- IKU 12 — Kesejahteraan dosen
CREATE TABLE IF NOT EXISTS iku12_kesejahteraan_dosen (
    dosen_id                 VARCHAR(10) NOT NULL REFERENCES lecturers(dosen_id),
    program_id               VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    tahun                    SMALLINT    NOT NULL,
    kategori_tunjangan       VARCHAR(30),
    ikut_pengembangan_karir  BOOLEAN,
    status_perlindungan      VARCHAR(50),
    ada_rencana_peningkatan  BOOLEAN,
    PRIMARY KEY (dosen_id, tahun)
);

-- ---------------------------------------------------------------------
-- D. IKU PILIHAN
-- ---------------------------------------------------------------------

-- IKU 4 — Rekognisi dosen
CREATE TABLE IF NOT EXISTS iku4_rekognisi_dosen (
    id               SERIAL PRIMARY KEY,
    dosen_id         VARCHAR(10) NOT NULL REFERENCES lecturers(dosen_id),
    program_id       VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    tahun            SMALLINT    NOT NULL,
    jenis_rekognisi  VARCHAR(60),
    tingkat          VARCHAR(20) CHECK (tingkat IN ('Nasional','Internasional')),
    deskripsi        TEXT
);

-- IKU 6 — Publikasi internasional
CREATE TABLE IF NOT EXISTS iku6_publikasi (
    id             SERIAL PRIMARY KEY,
    dosen_id       VARCHAR(10) NOT NULL REFERENCES lecturers(dosen_id),
    program_id     VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    tahun          SMALLINT    NOT NULL,
    judul          VARCHAR(300),
    indeks         VARCHAR(20) CHECK (indeks IN ('Scopus','WoS','Sinta 1-2','Lainnya')),
    jumlah_sitasi  INTEGER DEFAULT 0
);

-- IKU 8 — SDM dalam kebijakan
CREATE TABLE IF NOT EXISTS iku8_sdm_kebijakan (
    id                  SERIAL PRIMARY KEY,
    dosen_id            VARCHAR(10) NOT NULL REFERENCES lecturers(dosen_id),
    program_id          VARCHAR(10) NOT NULL REFERENCES programs(program_id),
    tahun               SMALLINT    NOT NULL,
    jenis_keterlibatan  VARCHAR(60),
    instansi            VARCHAR(100),
    output              VARCHAR(60)
);

-- IKU 11 — Tata kelola berintegritas (6 komponen sesuai Kepmen)
CREATE TABLE IF NOT EXISTS iku11_tata_kelola (
    id                 SERIAL PRIMARY KEY,
    tahun              SMALLINT    NOT NULL,
    kategori           VARCHAR(40) NOT NULL
                       CHECK (kategori IN ('Audit Keuangan','SAKIP','Integritas Akademik',
                                           'Pencegahan Kekerasan (PPKS)','Anti Narkoba',
                                           'Anti Korupsi')),
    skor_atau_status   VARCHAR(20)
                       CHECK (skor_atau_status IN ('Kurang','Cukup','Baik','Sangat Baik')),
    skor_numerik       SMALLINT,
    ada_dokumen_bukti  BOOLEAN,
    UNIQUE (tahun, kategori)
);

-- IKU 10 (Zona Integritas WBK/WBBM) sengaja TIDAK dibuat sebagai tabel:
-- indikator ini hanya berlaku bagi PTN/instansi pemerintah. Statusnya
-- tetap tercatat di iku_target agar 12 IKU terdokumentasi utuh.

-- ---------------------------------------------------------------------
-- E. METADATA & TARGET
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS iku_target (
    iku_no        SMALLINT     NOT NULL,
    nama_iku      VARCHAR(60)  NOT NULL,
    status_pts    VARCHAR(30)  NOT NULL,   -- Wajib / Pilihan / Tidak Berlaku (PTS)
    tabel_sumber  VARCHAR(80),
    formula       TEXT,
    satuan        VARCHAR(20),
    tahun         SMALLINT     NOT NULL,
    target        NUMERIC(10,2),
    keterangan    TEXT,
    PRIMARY KEY (iku_no, tahun)
);

-- ---------------------------------------------------------------------
-- F. INDEKS
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_enroll_tahun   ON student_enrollment (tahun);
CREATE INDEX IF NOT EXISTS idx_aee_tahun      ON iku1_aee (tahun_lulus);
CREATE INDEX IF NOT EXISTS idx_pub_tahun      ON iku6_publikasi (tahun, indeks);
CREATE INDEX IF NOT EXISTS idx_pub_prog       ON iku6_publikasi (program_id);
CREATE INDEX IF NOT EXISTS idx_rek_prog       ON iku4_rekognisi_dosen (program_id, tahun);
CREATE INDEX IF NOT EXISTS idx_sdm_prog       ON iku8_sdm_kebijakan (program_id, tahun);
CREATE INDEX IF NOT EXISTS idx_kesra_tahun    ON iku12_kesejahteraan_dosen (tahun, program_id);
CREATE INDEX IF NOT EXISTS idx_ks_status      ON iku5_kerjasama (status, tahun_mulai);
CREATE INDEX IF NOT EXISTS idx_sdg_tahun      ON iku7_sdgs (tahun, sdg_terkait);

-- ---------------------------------------------------------------------
-- G. VIEW SIAP-PAKAI UNTUK SUPERSET
-- Dataset di Superset sebaiknya menunjuk ke view ini, bukan ke tabel mentah,
-- supaya definisi indikator hanya ada di satu tempat.
-- ---------------------------------------------------------------------

-- IKU 1: AEE = lulusan / (mahasiswa aktif + lulusan) x 100
CREATE OR REPLACE VIEW v_iku1_aee AS
SELECT e.program_id, p.faculty_id, e.tahun,
       e.mahasiswa_aktif, e.mahasiswa_baru, e.lulus, e.do_count,
       a.lulus_tepat_waktu, a.lulus_terlambat,
       ROUND(100.0 * e.lulus / NULLIF(e.mahasiswa_aktif + e.lulus, 0), 2) AS aee_pct,
       ROUND(100.0 * a.lulus_tepat_waktu / NULLIF(a.lulus_total, 0), 2)   AS tepat_waktu_pct,
       ROUND(100.0 * e.do_count / NULLIF(e.mahasiswa_aktif, 0), 2)        AS do_pct
FROM student_enrollment e
JOIN programs p  ON p.program_id = e.program_id
JOIN iku1_aee a  ON a.program_id = e.program_id AND a.tahun_lulus = e.tahun;

-- IKU 2: % lulusan terserap
CREATE OR REPLACE VIEW v_iku2_terserap AS
SELECT t.program_id, p.faculty_id, t.tahun_lulus,
       t.jumlah_lulusan, t.jumlah_responden, t.response_rate_pct,
       ROUND(100.0 * (t.bekerja + t.wirausaha + t.lanjut_studi)
             / NULLIF(t.jumlah_responden, 0), 2) AS terserap_pct,
       t.waktu_tunggu_rata2_bulan
FROM iku2_tracer_study t
JOIN programs p ON p.program_id = t.program_id;

-- IKU 3: intensitas partisipasi per 100 mahasiswa aktif
CREATE OR REPLACE VIEW v_iku3_aktivitas AS
SELECT a.program_id, p.faculty_id, a.tahun, a.mahasiswa_aktif,
       (a.ikut_kompetisi + a.ikut_pertukaran_pelajar + a.ikut_riset_dosen
        + a.ikut_pengabdian + a.ikut_magang_bersertifikat) AS total_partisipasi,
       ROUND(100.0 * (a.ikut_kompetisi + a.ikut_pertukaran_pelajar + a.ikut_riset_dosen
             + a.ikut_pengabdian + a.ikut_magang_bersertifikat)
             / NULLIF(a.mahasiswa_aktif, 0), 2) AS partisipasi_per_100_mhs,
       (a.menang_prestasi_nasional + a.menang_prestasi_internasional) AS total_prestasi
FROM iku3_aktivitas_mahasiswa a
JOIN programs p ON p.program_id = a.program_id;

-- IKU 5: % kerja sama aktif yang berujung hilirisasi
CREATE OR REPLACE VIEW v_iku5_hilirisasi AS
SELECT tahun_mulai AS tahun, jenis_mitra,
       COUNT(*)                                    AS jumlah_kerjasama,
       COUNT(*) FILTER (WHERE status = 'Aktif')    AS kerjasama_aktif,
       COUNT(*) FILTER (WHERE ada_hilirisasi)      AS dengan_hilirisasi,
       ROUND(100.0 * COUNT(*) FILTER (WHERE ada_hilirisasi)
             / NULLIF(COUNT(*), 0), 2)             AS hilirisasi_pct,
       SUM(nilai_kontrak_rupiah)                   AS total_nilai_kontrak
FROM iku5_kerjasama
GROUP BY tahun_mulai, jenis_mitra;

-- IKU 9: porsi pendapatan non-UKT
CREATE OR REPLACE VIEW v_iku9_non_ukt AS
SELECT u.tahun, u.pendapatan_ukt_rupiah, u.pendapatan_non_ukt_rupiah,
       u.total_pendapatan_rupiah, u.porsi_non_ukt_pct,
       n.sumber, n.jumlah_rupiah,
       ROUND(100.0 * n.jumlah_rupiah / NULLIF(u.pendapatan_non_ukt_rupiah, 0), 2)
           AS kontribusi_sumber_pct
FROM iku9_pendapatan_ukt u
JOIN iku9_pendapatan_non_ukt n ON n.tahun = u.tahun;

-- IKU 12: % dosen dengan perlindungan penuh & pengembangan karier
CREATE OR REPLACE VIEW v_iku12_kesejahteraan AS
SELECT k.tahun, k.program_id, p.faculty_id,
       COUNT(*) AS total_dosen,
       ROUND(100.0 * COUNT(*) FILTER (
             WHERE k.status_perlindungan = 'BPJS Kesehatan & Ketenagakerjaan')
             / NULLIF(COUNT(*), 0), 2) AS perlindungan_penuh_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE k.ikut_pengembangan_karir)
             / NULLIF(COUNT(*), 0), 2) AS pengembangan_karir_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE k.kategori_tunjangan <> 'Tidak Ada')
             / NULLIF(COUNT(*), 0), 2) AS penerima_tunjangan_pct
FROM iku12_kesejahteraan_dosen k
JOIN programs p ON p.program_id = k.program_id
GROUP BY k.tahun, k.program_id, p.faculty_id;

COMMIT;
