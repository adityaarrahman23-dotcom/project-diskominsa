import streamlit as st
import pandas as pd
import numpy as np
import io
import time
import re

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Master Data Aggregator", 
    page_icon="🔄", 
    layout="wide"
)

# --- FUNGSI LOGIKA PERHITUNGAN ---
def hitung_skor(df):
    """Fungsi untuk menghitung RB(3), RS(2), RR(1) dari data mentah"""
    # Pastikan kolom Jumlah adalah angka
    df['Jumlah'] = pd.to_numeric(df['Jumlah'], errors='coerce').fillna(0)
    # Bersihkan spasi dan jadikan huruf besar agar cocok
    df['Kategori Kerusakan'] = df['Kategori Kerusakan'].astype(str).str.strip().str.upper()
    
    # Gabungkan Objek dan Satuan jika kolom Satuan tersedia
    if 'Satuan' in df.columns:
        df['Objek_Full'] = df['Objek'].astype(str) + " (" + df['Satuan'].astype(str) + ")"
    else:
        df['Objek_Full'] = df['Objek'].astype(str)
    
    # Logika Perkalian (RB=3, RS=2, RR=1)
    # Jika user menginput angka di 'Kategori Kerusakan' (misal: 1, 2, 3), sistem akan mendeteksi
    kondisi = [
        (df['Kategori Kerusakan'].isin(['RB', '3', 'BERAT'])),
        (df['Kategori Kerusakan'].isin(['RS', '2', 'SEDANG'])),
        (df['Kategori Kerusakan'].isin(['RR', '1', 'RINGAN']))
    ]
    pilihan = [df['Jumlah'] * 3, df['Jumlah'] * 2, df['Jumlah'] * 1]
    
    df['Nilai_Kalkulasi'] = np.select(kondisi, pilihan, default=0)
    return df

def normalisasi_kolom(df):
    """Memetakan variasi nama kolom ke format standar aplikasi"""
    
    # 1. Hapus kolom yang mengandung kata 'kode' karena biasanya berisi ID angka bukan nama
    cols_to_drop = [c for c in df.columns if 'kode' in str(c).lower()]
    df = df.drop(columns=cols_to_drop)
    
    # 2. Bersihkan nama kolom mentah yang tersisa
    new_cols = []
    for c in df.columns:
        # Ganti '/' dengan spasi, hapus kutipan, kecilkan huruf
        clean_c = str(c).lower().strip().replace('"', '').replace("'", "").replace('/', ' ')
        # Gunakan regex untuk menghapus spasi ganda/berlebih menjadi spasi tunggal
        clean_c = re.sub(r'\s+', ' ', clean_c)
        new_cols.append(clean_c)
    
    df.columns = new_cols
    
    # Mapping variasi berdasarkan input terbaru user
    mapping = {
        'nama kabupaten kota': 'Nama Kabupaten/Kota',
        'kabupaten': 'Nama Kabupaten/Kota',
        'kota': 'Nama Kabupaten/Kota',
        'nama kabupaten': 'Nama Kabupaten/Kota',
        'nama kota': 'Nama Kabupaten/Kota',
        'kabupaten kota': 'Nama Kabupaten/Kota',
        'nama kecamatan': 'Nama Kecamatan',
        'kecamatan': 'Nama Kecamatan',
        'kegiatan objek': 'Objek',      # Sesuai input: Kegiatan/ Objek
        'objek': 'Objek',
        'nama objek': 'Objek',
        'tingkat kerusakan': 'Kategori Kerusakan', # Sesuai input: Tingkat Kerusakan
        'kerusakan': 'Kategori Kerusakan',
        'kategori kerusakan': 'Kategori Kerusakan',
        'jumlah volume': 'Jumlah',      # Sesuai input: Jumlah/ volume
        'jumlah': 'Jumlah',
        'qty': 'Jumlah',
        'volume': 'Jumlah',
        'satuan': 'Satuan'
    }
    
    # Rename kolom
    df = df.rename(columns=mapping)
    
    # Ambil kolom pertama jika ada duplikasi penamaan setelah normalisasi
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    return df

# --- INISIALISASI PENYIMPANAN SEMENTARA (SESSION STATE) ---
if 'db_master' not in st.session_state:
    st.session_state.db_master = pd.DataFrame(columns=['Nama Kabupaten/Kota', 'Nama Kecamatan', 'Objek', 'Nilai_Kalkulasi'])
if 'riwayat_file' not in st.session_state:
    st.session_state.riwayat_file = []

# --- HEADER APLIKASI ---
st.title("🔄 Master Agregasi & Penggabung Data")
st.markdown("""
Aplikasi ini dioptimalkan untuk format kolom: 
`Nama Kabupaten/ Kota`, `Kegiatan/ Objek`, `Tingkat Kerusakan`, dan `Jumlah/ volume`.
""")

# Tombol Reset
col_kosong, col_reset = st.columns([8, 1])
with col_reset:
    if st.button("🗑️ Reset Semua", help="Hapus semua data di memori aplikasi"):
        st.session_state.db_master = pd.DataFrame(columns=['Nama Kabupaten/Kota', 'Nama Kecamatan', 'Objek', 'Nilai_Kalkulasi'])
        st.session_state.riwayat_file = []
        st.rerun()

# --- PEMBAGIAN 3 TAB UTAMA ---
tab1, tab2, tab3 = st.tabs([
    "📥 1. Input Data Mentah", 
    "📂 2. Gabung Hasil Sebelumnya", 
    "📊 3. Dashboard Hasil Gabungan"
])

# ==========================================
# TAB 1: INPUT DATA MENTAH
# ==========================================
with tab1:
    st.header("Masukkan File Mentah")
    st.info("Sistem otomatis membuang kolom 'Kode' dan fokus pada nama wilayah serta perhitungan skor kerusakan.")
    
    file_mentah = st.file_uploader("Pilih File Mentah (CSV/Excel)", type=["csv", "xlsx"], accept_multiple_files=True, key="mentah")
    
    if st.button("🚀 Proses & Konversi Data", type="primary"):
        if file_mentah:
            data_baru_mentah = []
            file_sukses = 0
            
            for f in file_mentah:
                if f.name not in st.session_state.riwayat_file:
                    try:
                        df = None
                        if f.name.endswith('.csv'):
                            f.seek(0)
                            # sep=None mendeteksi apakah pemisah itu ; atau , otomatis
                            df = pd.read_csv(f, sep=None, engine='python', encoding='utf-8')
                        else:
                            df = pd.read_excel(f)
                        
                        if df is not None:
                            # Normalisasi kolom & Pembersihan
                            df = normalisasi_kolom(df)
                            
                            kolom_wajib = ['Nama Kabupaten/Kota', 'Nama Kecamatan', 'Objek', 'Kategori Kerusakan', 'Jumlah']
                            missing_cols = [c for c in kolom_wajib if c not in df.columns]
                            
                            if not missing_cols:
                                df_skor = hitung_skor(df)
                                # Grouping awal per file
                                df_ringkas = df_skor.groupby(['Nama Kabupaten/Kota', 'Nama Kecamatan', 'Objek_Full'])['Nilai_Kalkulasi'].sum().reset_index()
                                df_ringkas.rename(columns={'Objek_Full': 'Objek'}, inplace=True)
                                
                                data_baru_mentah.append(df_ringkas)
                                st.session_state.riwayat_file.append(f.name)
                                file_sukses += 1
                            else:
                                st.error(f"File '{f.name}' ditolak. Kolom wajib tidak ditemukan: {', '.join(missing_cols)}. Kolom yang terdeteksi: {list(df.columns)}")
                    except Exception as e:
                        st.error(f"Gagal membaca {f.name}: {e}")
            
            if data_baru_mentah:
                gabungan = pd.concat(data_baru_mentah + [st.session_state.db_master], ignore_index=True)
                st.session_state.db_master = gabungan.groupby(['Nama Kabupaten/Kota', 'Nama Kecamatan', 'Objek'])['Nilai_Kalkulasi'].sum().reset_index()
                st.success(f"Berhasil memproses {file_sukses} file!")
        else:
            st.warning("Pilih file terlebih dahulu.")

# ==========================================
# TAB 2: GABUNG HASIL SEBELUMNYA
# ==========================================
with tab2:
    st.header("Gabungkan dengan File Hasil Lama")
    file_lama = st.file_uploader("Pilih File Hasil Agregasi (.xlsx)", type=["xlsx"], accept_multiple_files=True, key="lama")
    
    if st.button("🔗 Gabungkan File Lama", type="primary"):
        if file_lama:
            data_lama_list = []
            file_sukses_lama = 0
            for f in file_lama:
                if f.name not in st.session_state.riwayat_file:
                    try:
                        df_excel_lama = pd.read_excel(f)
                        id_vars_cols = [df_excel_lama.columns[0], df_excel_lama.columns[1]]
                        
                        # Hapus TOTAL KESELURUHAN jika ada di file lama agar tidak duplikat/salah hitung
                        if 'TOTAL KESELURUHAN' in df_excel_lama.columns:
                            df_excel_lama = df_excel_lama.drop(columns=['TOTAL KESELURUHAN'])
                            
                        df_unpivot = df_excel_lama.melt(id_vars=id_vars_cols, var_name='Objek', value_name='Nilai_Kalkulasi')
                        df_unpivot.columns = ['Nama Kabupaten/Kota', 'Nama Kecamatan', 'Objek', 'Nilai_Kalkulasi']
                        df_unpivot = df_unpivot[df_unpivot['Nilai_Kalkulasi'] > 0]
                        
                        data_lama_list.append(df_unpivot)
                        st.session_state.riwayat_file.append(f.name)
                        file_sukses_lama += 1
                    except Exception as e:
                        st.error(f"Gagal menggabungkan {f.name}: {e}")
            
            if data_lama_list:
                gabungan_lama = pd.concat(data_lama_list + [st.session_state.db_master], ignore_index=True)
                st.session_state.db_master = gabungan_lama.groupby(['Nama Kabupaten/Kota', 'Nama Kecamatan', 'Objek'])['Nilai_Kalkulasi'].sum().reset_index()
                st.success(f"Berhasil melebur {file_sukses_lama} file hasil lama!")

# ==========================================
# TAB 3: DASHBOARD HASIL & DOWNLOAD
# ==========================================
with tab3:
    if not st.session_state.db_master.empty:
        st.header("📊 Hasil Akhir Konsolidasi")
        
        # Susun ulang tabel menjadi format Excel (Pivot)
        df_final = st.session_state.db_master.pivot(
            index=['Nama Kabupaten/Kota', 'Nama Kecamatan'], 
            columns='Objek', 
            values='Nilai_Kalkulasi'
        ).fillna(0).reset_index()
        
        # Objek kolom tanpa variabel total keseluruhan
        objek_cols = [c for c in df_final.columns if c not in ['Nama Kabupaten/Kota', 'Nama Kecamatan']]
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Wilayah", len(df_final))
        col_m2.metric("Total Objek Unik", len(objek_cols))
        col_m3.metric("Skor Kumulatif", f"{int(st.session_state.db_master['Nilai_Kalkulasi'].sum()):,}")
        
        st.divider()
        kata_kunci = st.text_input("🔍 Cari Kabupaten atau Kecamatan...")
        df_tampil = df_final.copy()
        if kata_kunci:
            mask = (df_tampil['Nama Kabupaten/Kota'].astype(str).str.contains(kata_kunci, case=False)) | \
                   (df_tampil['Nama Kecamatan'].astype(str).str.contains(kata_kunci, case=False))
            df_tampil = df_tampil[mask]
            
        st.dataframe(df_tampil, use_container_width=True)
        
        st.divider()
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_tampil.to_excel(writer, index=False, sheet_name='Data_Gabungan')
            st.download_button(
                label="⬇️ Unduh File Master Agregasi (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Master_Agregasi_{time.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Gagal membuat file Excel: {e}")
    else:
        st.info("Sistem kosong. Silahkan proses data di Tab 1 atau Tab 2 terlebih dahulu.")