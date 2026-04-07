import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import requests
from io import BytesIO
import time
from datetime import datetime

# ==========================================
# 1. KONFIGURASI HALAMAN & HIDE GITHUB LOGO
# ==========================================
st.set_page_config(page_title="Web Say Bread", layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .block-container {
                padding-top: 2rem;
                padding-bottom: 0rem;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================
# 2. KONFIGURASI CLOUDINARY
# ==========================================
cloudinary.config(
    cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"],
    api_key = st.secrets["CLOUDINARY_API_KEY"],
    api_secret = st.secrets["CLOUDINARY_API_SECRET"],
    secure = True
)

PUBLIC_FILE_ID = "data_saybread.xlsx"
PUBLIC_PERIODE_ID = "periode_saybread.txt" # File pendamping untuk menyimpan tanggal

st.title("🍞 Portal Say Bread")

# ==========================================
# 3. MENU UTAMA MENGGUNAKAN TABS
# ==========================================
tab_monitoring, tab_admin = st.tabs(["📊 Monitoring Say Bread", "🔐 Admin"])

# ------------------------------------------
# ISI TAB 1: MONITORING SAY BREAD
# ------------------------------------------
with tab_monitoring:
    st.subheader("Pencarian Data Toko")
    
    cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"]
    base_url = f"https://res.cloudinary.com/{cloud_name}/raw/upload/{PUBLIC_FILE_ID}"
    periode_url = f"https://res.cloudinary.com/{cloud_name}/raw/upload/{PUBLIC_PERIODE_ID}"
    
    fetch_url = f"{base_url}?t={int(time.time())}"
    fetch_periode_url = f"{periode_url}?t={int(time.time())}"

    try:
        # Mengambil file Excel
        response = requests.get(fetch_url)
        
        # Mengambil file Teks Periode (Jika ada)
        teks_periode = "Belum diatur"
        try:
            resp_periode = requests.get(fetch_periode_url)
            if resp_periode.status_code == 200:
                teks_periode = resp_periode.text
        except:
            pass # Abaikan jika file periode belum dibuat oleh admin
            
        if response.status_code == 200:
            df = pd.read_excel(BytesIO(response.content))
            df['Toko'] = df['Toko'].astype(str).str.strip().str.upper()

            # 1. Menampilkan Label Periode Data
            st.markdown(f"#### 📅 Periode Data: `{teks_periode}`")
            st.write("") # Spasi kosong

            # 2. Kolom Input Kode Toko
            input_toko = st.text_input("🔍 Masukkan 4 Digit Kode Toko:", max_chars=4, placeholder="Contoh: F08C").upper()

            if input_toko:
                if len(input_toko) < 4:
                    st.error("⚠️ Error: Kode toko harus terdiri dari 4 digit alfanumerik!")
                elif len(input_toko) == 4:
                    filtered_df = df[df['Toko'] == input_toko]

                    if filtered_df.empty:
                        st.warning(f"⚠️ Data untuk kode toko '{input_toko}' tidak ditemukan.")
                    else:
                        st.markdown("---")
                        
                        # Label Nama, AM, dan AS
                        nama_toko = filtered_df.iloc[0]['Nama']
                        am_toko = filtered_df.iloc[0]['AM']
                        as_toko = filtered_df.iloc[0]['AS']

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.success(f"**🏷️ Nama Toko:**\n\n{nama_toko}")
                        with col2:
                            st.info(f"**👤 AM:**\n\n{am_toko}")
                        with col3:
                            st.warning(f"**👥 AS:**\n\n{as_toko}")
                        
                        st.write("")

                        # Tampilan Data Terbatas di Layar
                        kolom_tampil = [
                            'PLU Jual', 'Deskripsi', 'Qty Produksi', 'Qty Sales', 
                            'QTY Total Rusak', '% Rusak By Qty', 'Avg Produksi', 
                            'Avg Sales', 'Avg Rusak'
                        ]
                        
                        kolom_tersedia = [col for col in kolom_tampil if col in filtered_df.columns]
                        display_df = filtered_df[kolom_tersedia]

                        st.write(f"**Tabel Data Item - {nama_toko}**")
                        
                        # 3. Menampilkan dataframe dengan Format 2 digit desimal
                        st.dataframe(
                            display_df, 
                            hide_index=True, 
                            use_container_width=True,
                            column_config={
                                # Mengatur kolom-kolom persentase & rata-rata menjadi 2 digit di belakang koma (%.2f)
                                "% Rusak By Qty": st.column_config.NumberColumn(format="%.2f"),
                                "Avg Produksi": st.column_config.NumberColumn(format="%.2f"),
                                "Avg Sales": st.column_config.NumberColumn(format="%.2f"),
                                "Avg Rusak": st.column_config.NumberColumn(format="%.2f")
                            }
                        )

                        st.markdown("<br>", unsafe_allow_html=True)

                        # Tombol Download Data Lengkap
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            filtered_df.to_excel(writer, index=False, sheet_name='Data_Toko')
                        excel_data = output.getvalue()

                        st.download_button(
                            label=f"📥 Download Data Lengkap {input_toko} (Excel)",
                            data=excel_data,
                            file_name=f"Data_SayBread_{input_toko}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary"
                        )
        else:
            st.info("ℹ️ Belum ada data sumber yang diunggah oleh Admin.")
            
    except Exception as e:
        st.error(f"Terjadi kesalahan sistem: {e}")


# ------------------------------------------
# ISI TAB 2: ADMIN AREA
# ------------------------------------------
with tab_admin:
    st.subheader("Halaman Admin")
    
    password_input = st.text_input("Masukkan Password Admin:", type="password", key="admin_pass")
    
    if password_input == "icnbr034":
        st.success("🔓 Login Berhasil! Selamat datang Admin.")
        st.markdown("---")
        
        # Input Kalender (Bisa pilih 1 tanggal atau rentang tanggal)
        st.write("**1. Tentukan Periode Data:**")
        input_periode = st.date_input("Pilih Tanggal Periode (Bisa pilih rentang/range):", [])
        
        # Konversi input kalender menjadi teks
        if len(input_periode) == 2:
            teks_periode_upload = f"{input_periode[0].strftime('%d %B %Y')} - {input_periode[1].strftime('%d %B %Y')}"
        elif len(input_periode) == 1:
            teks_periode_upload = f"{input_periode[0].strftime('%d %B %Y')}"
        else:
            teks_periode_upload = "Periode Tidak Ditentukan"

        st.write("**2. Upload File Excel Master:**")
        uploaded_file = st.file_uploader("Pilih file Excel", type=["xlsx", "xls"], key="uploader")
        
        if uploaded_file is not None:
            if st.button("📤 Upload & Perbarui Data"):
                with st.spinner("Mengunggah data ke Cloudinary..."):
                    try:
                        # Upload File Excel
                        cloudinary.uploader.upload(
                            uploaded_file,
                            resource_type="raw",
                            public_id=PUBLIC_FILE_ID,
                            overwrite=True,
                            invalidate=True
                        )
                        
                        # Upload Teks Periode sebagai file text ke Cloudinary
                        cloudinary.uploader.upload(
                            BytesIO(teks_periode_upload.encode('utf-8')),
                            resource_type="raw",
                            public_id=PUBLIC_PERIODE_ID,
                            overwrite=True,
                            invalidate=True
                        )
                        
                        st.success("✅ File dan Periode berhasil diperbarui! Silakan cek tab Monitoring.")
                    except Exception as e:
                        st.error(f"❌ Gagal mengunggah file: {e}")
                        
    elif password_input != "":
        st.error("❌ Password Salah! Anda tidak memiliki akses.")
