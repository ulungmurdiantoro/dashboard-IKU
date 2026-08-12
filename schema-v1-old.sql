-- =========================================================================
-- SKEMA DATABASE: DASHBOARD IR + IKU KEMDIKTISAINTEK
-- Universitas: Sampoerna University (contoh)
-- Regulasi acuan: Kepmendiktisaintek No. 358/M/KEP/2025 (12 IKU, berlaku 2026)
-- =========================================================================

-- =========================================================================
-- BAGIAN 0: TABEL REFERENSI INTI
-- =========================================================================

CREATE TABLE faculties (
    faculty_id      VARCHAR(10) PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    short_name      VARCHAR(10)
);

CREATE TABLE programs (
    program_id      VARCHAR(10) PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    faculty_id      VARCHAR(10) REFERENCES faculties(faculty_id),
    jenjang         VARCHAR(10) DEFAULT 'S1'   -- S1/S2/S3/D3/D4
);

CREATE TABLE lecturers (
    dosen_id        VARCHAR(15) PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    program_id      VARCHAR(10) REFERENCES programs(program_id),
    jabatan_akademik VARCHAR(30),              -- Asisten Ahli/Lektor/Lektor Kepala/Guru Besar
    status_sertifikasi VARCHAR(20),            -- Sudah/Belum
    pendidikan_terakhir VARCHAR(5),            -- S2/S3
    tahun_mulai_kerja INT
);

-- Tabel user untuk pemetaan Row-Level Security di Superset
CREATE TABLE dashboard_users (
    username        VARCHAR(30) PRIMARY KEY,
    role            VARCHAR(20) NOT NULL,      -- rektor/dekan/kaprodi/kabag
    faculty_id      VARCHAR(10) REFERENCES faculties(faculty_id),   -- NULL jika rektor
    program_id      VARCHAR(10) REFERENCES programs(program_id),   -- NULL kecuali kaprodi
    bureau          VARCHAR(30)                -- 'akademik' / 'admisi', khusus kabag
);


-- =========================================================================
-- BAGIAN 1: MODUL INSTITUTIONAL RESEARCH (IR) INTI
-- (Admisi, Kelulusan, Retensi -- sudah ada polanya di POC sebelumnya)
-- =========================================================================

CREATE TABLE admission_funnel (
    program_id      VARCHAR(10) REFERENCES programs(program_id),
    year            INT NOT NULL,
    complete        INT,        -- pendaftar complete application
    admitted        INT,        -- diterima
    enrolled        INT,        -- registrasi ulang / enrolled
    PRIMARY KEY (program_id, year)
);

CREATE TABLE demographics (
    program_id      VARCHAR(10) REFERENCES programs(program_id),
    year            INT NOT NULL,
    male_pct        NUMERIC(5,2),
    female_pct      NUMERIC(5,2),
    region_jkt_pct  NUMERIC(5,2),
    region_jabar_pct NUMERIC(5,2),
    region_other_pct NUMERIC(5,2),
    region_intl_pct NUMERIC(5,2),
    fee_paying_pct  NUMERIC(5,2),
    assisted_pct    NUMERIC(5,2),
    PRIMARY KEY (program_id, year)
);

CREATE TABLE graduation (
    program_id      VARCHAR(10) REFERENCES programs(program_id),
    grad_year       INT NOT NULL,
    grad_count      INT,
    avg_gpa         NUMERIC(3,2),
    ftic_pct        NUMERIC(5,2),       -- First Time in College
    transfer_pct    NUMERIC(5,2),
    avg_years       NUMERIC(3,2),       -- rata-rata lama studi
    PRIMARY KEY (program_id, grad_year)
);

CREATE TABLE retention (
    program_id      VARCHAR(10) REFERENCES programs(program_id),
    year            INT NOT NULL,
    year1_count     INT,
    year2_count     INT,
    rate            NUMERIC(5,4),
    PRIMARY KEY (program_id, year)
);


-- =========================================================================
-- BAGIAN 2: 7 IKU WAJIB (Kepmendiktisaintek No. 358/M/KEP/2025)
-- =========================================================================

-- IKU 1: AEE PT (Angka Efisiensi Edukasi) -- lulus tepat waktu
CREATE TABLE iku1_aee (
    program_id              VARCHAR(10) REFERENCES programs(program_id),
    tahun_lulus              INT NOT NULL,
    lulus_tepat_waktu        INT,
    lulus_total              INT,
    standar_masa_studi_semester INT DEFAULT 8,
    PRIMARY KEY (program_id, tahun_lulus)
);

-- IKU 2: Lulusan Terserap (Tracer Study, maks. 1 tahun setelah lulus)
CREATE TABLE iku2_tracer_study (
    program_id              VARCHAR(10) REFERENCES programs(program_id),
    tahun_lulus              INT NOT NULL,
    jumlah_responden         INT,
    bekerja                  INT,
    wirausaha                INT,
    lanjut_studi             INT,
    belum_bekerja            INT,
    waktu_tunggu_rata2_bulan NUMERIC(4,1),
    PRIMARY KEY (program_id, tahun_lulus)
);

-- IKU 3: Aktivitas & Prestasi Mahasiswa
CREATE TABLE iku3_aktivitas_mahasiswa (
    program_id              VARCHAR(10) REFERENCES programs(program_id),
    tahun                    INT NOT NULL,
    ikut_kompetisi           INT,
    menang_prestasi          INT,
    ikut_pertukaran_pelajar  INT,
    ikut_riset_dosen         INT,
    ikut_organisasi          INT,
    ikut_pengabdian          INT,
    PRIMARY KEY (program_id, tahun)
);

-- IKU 5: Kerja Sama & Hilirisasi
CREATE TABLE iku5_kerjasama (
    kerjasama_id     SERIAL PRIMARY KEY,
    nama_mitra        VARCHAR(150),
    jenis_mitra        VARCHAR(30),     -- Industri/Pemerintah/Sekolah/Lembaga/Lainnya
    program_terkait_id VARCHAR(10) REFERENCES programs(program_id),
    tahun_mulai        INT,
    tahun_berakhir      INT,
    status              VARCHAR(20),     -- Aktif/Selesai
    ada_hilirisasi       BOOLEAN,         -- apakah hasil riset/inovasi dimanfaatkan nyata
    deskripsi_dampak     TEXT
);

-- IKU 7: Kontribusi SDGs
CREATE TABLE iku7_sdgs (
    kegiatan_id       SERIAL PRIMARY KEY,
    judul              VARCHAR(200),
    sdg_terkait         VARCHAR(10),     -- misal 'SDG 1','SDG 4','SDG 17'
    tahun               INT,
    unit_pelaksana       VARCHAR(10) REFERENCES faculties(faculty_id),
    jumlah_penerima_manfaat INT
);

-- IKU 9: Pendapatan Non-UKT
CREATE TABLE iku9_pendapatan_non_ukt (
    id                 SERIAL PRIMARY KEY,
    tahun               INT NOT NULL,
    sumber               VARCHAR(50),   -- Bisnis Kampus/Pelatihan/Konsultasi/Hibah/Kerjasama/Unit Usaha
    jumlah_rupiah         BIGINT
);

-- IKU 12: Kesejahteraan Dosen
CREATE TABLE iku12_kesejahteraan_dosen (
    dosen_id            VARCHAR(15) REFERENCES lecturers(dosen_id),
    tahun                 INT NOT NULL,
    kategori_tunjangan     VARCHAR(30),  -- Fungsional/Sertifikasi/Kinerja/dll
    ikut_pengembangan_karir BOOLEAN,     -- pelatihan/studi lanjut/dll
    status_perlindungan     VARCHAR(40), -- BPJS Kesehatan/Ketenagakerjaan/Keduanya/Tidak Ada
    PRIMARY KEY (dosen_id, tahun)
);


-- =========================================================================
-- BAGIAN 3: 4 IKU PILIHAN (opsional, prioritas Fase berikutnya)
-- =========================================================================

-- IKU 4: Rekognisi Dosen
CREATE TABLE iku4_rekognisi_dosen (
    id              SERIAL PRIMARY KEY,
    dosen_id         VARCHAR(15) REFERENCES lecturers(dosen_id),
    tahun             INT,
    jenis_rekognisi    VARCHAR(50),  -- Penghargaan Internasional/Kepakaran/Sitasi/dll
    deskripsi          TEXT
);

-- IKU 6: Publikasi Internasional (proxy data publik tersedia via SINTA)
CREATE TABLE iku6_publikasi (
    id              SERIAL PRIMARY KEY,
    dosen_id         VARCHAR(15) REFERENCES lecturers(dosen_id),
    tahun             INT,
    judul              VARCHAR(250),
    indeks             VARCHAR(20),   -- Scopus/WoS/Lainnya
    jumlah_sitasi       INT
);

-- IKU 8: SDM dalam Kebijakan
CREATE TABLE iku8_sdm_kebijakan (
    id              SERIAL PRIMARY KEY,
    dosen_id         VARCHAR(15) REFERENCES lecturers(dosen_id),
    tahun             INT,
    jenis_keterlibatan  VARCHAR(80),  -- Penyusunan Kebijakan/Konsultasi Pemerintah/dll
    instansi            VARCHAR(150)
);

-- IKU 11: Tata Kelola Berintegritas
CREATE TABLE iku11_tata_kelola (
    id              SERIAL PRIMARY KEY,
    tahun             INT,
    kategori           VARCHAR(50),  -- Audit Keuangan/SAKIP/Integritas Akademik/Anti Korupsi/dll
    skor_atau_status    VARCHAR(50)
);

-- Catatan: IKU 10 (Zona Integritas) TIDAK dibuat -- khusus PTN, tidak berlaku untuk PTS.
