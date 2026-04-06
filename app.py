import streamlit as st
import pandas as pd
import numpy as np
import io
import time

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Master Data Aggregator", 
    page_icon="🔄", 
    layout="wide"
)

# --- FUNGSI LOGIKA PERHITUNGAN ---
def hitung_skor(df):
    """Fungsi untuk menghitung RB(3), RS(2), RR(1) dari data mentah"""
    # Ubah jumlah ke numerik, yang bukan angka jadi 0
    df['Jumlah'] = pd.to_numeric(df['Jumlah'], errors='coerce').fillna(0)
    # Bersihkan spasi dan jadikan huruf besar agar cocok
    df['Kategori Kerusakan'] = df['Kategori Kerusakan'].astype(str).str.strip().str.upper()
    
    # Logika Perkalian
    kondisi = [
        (df['Kategori Kerusakan'] == 'RB'),
        (df['Kategori Kerusakan'] == 'RS'),
        (df['Kategori Kerusakan'] == 'RR')
    ]
    pilihan = [df['Jumlah'] * 3, df['Jumlah'] * 2, df['Jumlah'] * 1]
    
    df['Nilai_Kalkulasi'] = np.select(kondisi, pilihan, default=0)
    return df

# --- INISIALISASI PENYIMPANAN SEMENTARA (SESSION STATE) ---
# db_master menyimpan format panjang (Vertikal): Kecamatan | Objek | Nilai
if 'db_master' not in st.session_state:
    st.session_state.db_master = pd.DataFrame(columns=['Nama Kecamatan', 'Objek', 'Nilai_Kalkulasi'])
if 'riwayat_file' not in st.session_state:
    st.session_state.riwayat_file = []

# --- HEADER APLIKASI ---
st.title("🔄 Master Agregasi & Penggabung Data")
st.markdown("Aplikasi ini memungkinkan Anda memproses file mentah **DAN** menggabungkannya dengan file hasil agregasi dari sesi sebelumnya.")

# Tombol Reset di pojok kanan atas
col_kosong, col_reset = st.columns([8, 1])
with col_reset:
    if st.button("🗑️ Reset Semua", help="Hapus semua data di memori aplikasi"):
        st.session_state.db_master = pd.DataFrame(columns=['Nama Kecamatan', 'Objek', 'Nilai_Kalkulasi'])
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
    st.info("Upload file sumber yang memiliki kolom: **Nama Kecamatan, Objek, Kategori Kerusakan, dan Jumlah**.")
    
    file_mentah = st.file_uploader("Pilih File Mentah (CSV/Excel)", type=["csv", "xlsx"], accept_multiple_files=True, key="mentah")
    
    if st.button("🚀 Proses Data Mentah", type="primary"):
        if file_mentah:
            data_baru_mentah = []
            file_sukses = 0
            
            for f in file_mentah:
                # Cek agar tidak duplikat
                if f.name not in st.session_state.riwayat_file:
                    try:
                        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                        df.columns = df.columns.str.strip() # Bersihkan nama kolom
                        
                        if all(col in df.columns for col in ['Nama Kecamatan', 'Objek', 'Kategori Kerusakan', 'Jumlah']):
                            df_skor = hitung_skor(df)
                            
                            # Ringkas data per file (Group By)
                            df_ringkas = df_skor.groupby(['Nama Kecamatan', 'Objek'])['Nilai_Kalkulasi'].sum().reset_index()
                            data_baru_mentah.append(df_ringkas)
                            
                            st.session_state.riwayat_file.append(f.name)
                            file_sukses += 1
                        else:
                            st.error(f"Format kolom tidak sesuai pada file: {f.name}")
                    except Exception as e:
                        st.error(f"Gagal membaca {f.name}: {e}")
            
            # Gabungkan ke Master DB
            if data_baru_mentah:
                gabungan = pd.concat(data_baru_mentah + [st.session_state.db_master], ignore_index=True)
                # Group by ulang untuk menyatukan kecamatan & objek yang sama dari file yang berbeda
                st.session_state.db_master = gabungan.groupby(['Nama Kecamatan', 'Objek'])['Nilai_Kalkulasi'].sum().reset_index()
                st.success(f"Berhasil memproses dan menambahkan {file_sukses} file mentah!")
        else:
            st.warning("Pilih file terlebih dahulu.")

# ==========================================
# TAB 2: GABUNG HASIL SEBELUMNYA
# ==========================================
with tab2:
    st.header("Gabungkan dengan File Hasil Lama")
    st.info("Punya file Excel **hasil download agregasi dari aplikasi ini sebelumnya**? Upload di sini untuk digabungkan dengan data saat ini.")
    
    file_lama = st.file_uploader("Pilih File Hasil Agregasi (.xlsx)", type=["xlsx"], accept_multiple_files=True, key="lama")
    
    if st.button("🔗 Gabungkan File Lama", type="primary"):
        if file_lama:
            data_lama_list = []
            file_sukses_lama = 0
            
            for f in file_lama:
                if f.name not in st.session_state.riwayat_file:
                    try:
                        df_excel_lama = pd.read_excel(f)
                        nama_kolom_kecamatan = df_excel_lama.columns[0] # Asumsi kolom pertama pasti Kecamatan
                        
                        # Buang kolom 'TOTAL KESELURUHAN' jika ada (agar tidak dianggap sebagai 'Objek' saat di-unpivot)
                        if 'TOTAL KESELURUHAN' in df_excel_lama.columns:
                            df_excel_lama = df_excel_lama.drop(columns=['TOTAL KESELURUHAN'])
                            
                        # UNPIVOT (Melt): Merubah format kolom lebar kembali menjadi baris ke bawah
                        # Kolom-kolom objek di Excel lama akan berubah menjadi baris nilai di kolom 'Objek'
                        df_unpivot = df_excel_lama.melt(
                            id_vars=[nama_kolom_kecamatan], 
                            var_name='Objek', 
                            value_name='Nilai_Kalkulasi'
                        )
                        df_unpivot.columns = ['Nama Kecamatan', 'Objek', 'Nilai_Kalkulasi']
                        
                        # Buang nilai 0 atau NaN hasil dari unpivot (hemat memori)
                        df_unpivot = df_unpivot[df_unpivot['Nilai_Kalkulasi'] > 0]
                        
                        data_lama_list.append(df_unpivot)
                        st.session_state.riwayat_file.append(f.name)
                        file_sukses_lama += 1
                        
                    except Exception as e:
                        st.error(f"Gagal menggabungkan {f.name}: {e}")
            
            # Gabungkan ke Master DB
            if data_lama_list:
                gabungan_lama = pd.concat(data_lama_list + [st.session_state.db_master], ignore_index=True)
                st.session_state.db_master = gabungan_lama.groupby(['Nama Kecamatan', 'Objek'])['Nilai_Kalkulasi'].sum().reset_index()
                st.success(f"Berhasil melebur {file_sukses_lama} file hasil lama ke dalam database utama!")
        else:
            st.warning("Pilih file hasil lama terlebih dahulu.")

# ==========================================
# TAB 3: DASHBOARD HASIL & DOWNLOAD
# ==========================================
with tab3:
    if not st.session_state.db_master.empty:
        st.header("📊 Hasil Akhir Konsolidasi")
        
        # PIVOT KEMBALI UNTUK DITAMPILKAN (Format Melebar)
        df_final = st.session_state.db_master.pivot(
            index='Nama Kecamatan', 
            columns='Objek', 
            values='Nilai_Kalkulasi'
        ).fillna(0).reset_index()
        
        # Tambah kolom Total Keseluruhan untuk di Excel dan Tampilan
        df_final['TOTAL KESELURUHAN'] = df_final.iloc[:, 1:].sum(axis=1)
        
        # Metrik Ringkasan
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Kecamatan", len(df_final))
        col_m2.metric("Total Objek Terdampak", len(st.session_state.db_master['Objek'].unique()))
        col_m3.metric("Skor Kerusakan Kumulatif", f"{int(st.session_state.db_master['Nilai_Kalkulasi'].sum()):,}")
        
        st.divider()
        
        # Fitur Cari
        kata_kunci = st.text_input("🔍 Cari berdasarkan Nama Kecamatan...")
        df_tampil = df_final.copy()
        if kata_kunci:
            df_tampil = df_tampil[df_tampil['Nama Kecamatan'].str.contains(kata_kunci, case=False)]
            
        st.dataframe(df_tampil, use_container_width=True)
        
        st.divider()
        
        # Unduh Data
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
    else:
        st.info("Sistem kosong. Silahkan proses data di Tab 1 atau Tab 2 terlebih dahulu.")