import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import json
import time
import hashlib
from datetime import datetime, timedelta

# =================================================================
# 1. KONFIGURASI GLOBAL & CLOUDINARY
# =================================================================
try:
    cloudinary.config( 
      cloud_name = st.secrets["cloud_name"], 
      api_key = st.secrets["api_key"], 
      api_secret = st.secrets["api_secret"],
      secure = True
    )
except:
    st.error("Konfigurasi Secrets Cloudinary tidak ditemukan!")

st.set_page_config(page_title="Pareto NKL System", layout="wide")

USER_DB = "pareto_nkl/config/users_pareto_nkl.json"
MASTER_PATH = "pareto_nkl/master_pareto_nkl.xlsx"
MT_CONFIG = "pareto_nkl/config/maintenance_config.json"
MAINTENANCE_IMAGE = "https://res.cloudinary.com/dydpottpm/image/upload/v1769698444/What_is_Fraud__Definition_and_Examples_1_yck2yg.jpg"

# =================================================================
# 2. FUNGSI CORE & MAINTENANCE (RESTORASI SKRIP INTI)
# =================================================================

def get_maintenance_status():
    """PERMINTAAN 4: Cek status maintenance dari Cloudinary"""
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{MT_CONFIG}?t={int(time.time())}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("maintenance", False)
    except:
        return False
    return False

def set_maintenance_status(status):
    """PERMINTAAN 4: Set status maintenance oleh Admin"""
    try:
        config = {"maintenance": status, "updated_at": str(datetime.now())}
        cloudinary.uploader.upload(
            io.BytesIO(json.dumps(config).encode()), 
            resource_type="raw", public_id=MT_CONFIG, overwrite=True, invalidate=True
        )
        return True
    except:
        return False

def clear_all_caches():
    """Fungsi Skrip Inti: Bersihkan seluruh cache memori"""
    st.cache_data.clear()
    keys_to_delete = [k for k in st.session_state.keys() if any(x in k for x in ['ed_', 'result', 'data_toko', 'hash', 'user_db'])]
    for key in keys_to_delete:
        del st.session_state[key]

def get_user_db_safe():
    """PERMINTAAN 2: Penguatan Login dengan Retry 5x dan Session Cache"""
    if 'persistent_user_db' in st.session_state:
        return st.session_state.persistent_user_db
    
    url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
    for i in range(5):
        try:
            resp = requests.get(url_user, timeout=15)
            if resp.status_code == 200:
                db = resp.json()
                st.session_state.persistent_user_db = db
                return db
        except:
            time.sleep(1)
    return None

def clean_numeric(val):
    if pd.isna(val) or val == "": return 0.0
    s = str(val).replace(',', '').replace(' ', '')
    if '(' in s and ')' in s:
        s = '-' + s.replace('(', '').replace(')', '')
    try:
        return float(s)
    except: return 0.0

@st.cache_data(ttl=2) 
def get_master_data():
    try:
        v = datetime.now().strftime("%m-%Y") 
        res = cloudinary.api.resource(MASTER_PATH, resource_type="raw", invalidate=True)
        url_master = f"{res['secure_url']}?t={int(time.time())}"
        resp = requests.get(url_master)
        df = pd.read_excel(io.BytesIO(resp.content))
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # PERMINTAAN 1: Pastikan kolom baru terformat numerik
        numeric_target = ['QTY SO LALU', 'RP SO LALU', 'QTY SO NOW', 'RP SO NOW']
        for col in df.columns:
            if col in numeric_target:
                df[col] = df[col].apply(clean_numeric)
            else:
                df[col] = df[col].fillna("")
        
        if 'KETERANGAN' in df.columns:
            df['KETERANGAN'] = ""
        return df, v
    except: 
        return pd.DataFrame(), datetime.now().strftime("%m-%Y")

def get_existing_result(toko_code, version):
    try:
        p_id = f"pareto_nkl/hasil/Hasil_{toko_code}_v{version}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{p_id}?t={int(time.time())}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            df_res = pd.read_excel(io.BytesIO(resp.content))
            df_res.columns = [str(c).strip().upper() for c in df_res.columns]
            return df_res
        return None
    except: return None

def validate_file_exists_in_cloudinary(toko_code, version):
    """Fungsi Skrip Inti: Pengecekan fisik file agar tidak ghosting"""
    try:
        p_id = f"pareto_nkl/hasil/Hasil_{toko_code}_v{version}.xlsx"
        cloudinary.api.resource(p_id, resource_type="raw")
        return True
    except: return False

def update_user_db(new_db):
    try:
        cloudinary.uploader.upload(
            io.BytesIO(json.dumps(new_db).encode()), 
            resource_type="raw", public_id=USER_DB, overwrite=True, invalidate=True
        )
        st.session_state.persistent_user_db = new_db
        return True
    except: return False

def get_progress_data(df_m, version):
    if df_m.empty: return pd.DataFrame(), []
    try:
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/", max_results=500)
        files = res.get('resources', [])
        finished_stores = []
        suffix = f"_v{version}.xlsx"
        for f in files:
            p_id = f['public_id'].split('/')[-1]
            if p_id.endswith(suffix):
                finished_stores.append(p_id.replace("Hasil_", "").replace(suffix, ""))
        
        df_unique = df_m.drop_duplicates(subset=['KDTOKO']).copy()
        df_unique['STATUS'] = df_unique['KDTOKO'].apply(lambda x: 1 if x in finished_stores else 0)
        return df_unique, finished_stores
    except: return pd.DataFrame(), []

# Custom CSS Glassmorphism (Skrip Inti)
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(0,0,0,0.8), rgba(0,0,0,0.8)), 
                    url("https://res.cloudinary.com/dydpottpm/image/upload/v1769698444/What_is_Fraud__Definition_and_Examples_1_yck2yg.jpg");
        background-size: cover; background-attachment: fixed;
    }
    h1, h2, h3, p, span, label, .stTabs [data-baseweb="tab"] { color: white !important; text-shadow: 1px 1px 2px black; }
    div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] { background-color: rgba(255,255,255,0.05); border-radius: 10px; padding: 10px; }
    [data-testid="stMetric"] { background-color: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.2); }
    .nk-label { background-color: rgba(255, 75, 75, 0.2); padding: 10px; border-radius: 5px; border-left: 5px solid #ff4b4b; margin-bottom: 10px; }
    .nl-label { background-color: rgba(46, 204, 113, 0.2); padding: 10px; border-radius: 5px; border-left: 5px solid #2ecc71; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 3. ROUTING & MAINTENANCE (PERMINTAAN 4)
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "HOME"

# Check Maintenance Mode Real-time
is_mt = get_maintenance_status()

if is_mt and st.session_state.page not in ["ADMIN_AUTH", "ADMIN_PANEL"]:
    st.image(MAINTENANCE_IMAGE, use_container_width=True)
    st.error("### 🛠️ Mohon Maaf, Web sedang Maintenance")
    st.info("Kami sedang melakukan perbaikan sistem. Silakan coba lagi nanti.")
    if st.button("🛡️ Admin Login"): st.session_state.page = "ADMIN_AUTH"; st.rerun()
    st.stop()

# --- HALAMAN HOME (RESTORASI SKRIP INTI) ---
if st.session_state.page == "HOME":
    st.title("📑 Sistem Penjelasan Pareto NKL")
    df_m_prog, v_prog = get_master_data()
    if not df_m_prog.empty:
        df_u, finished_list = get_progress_data(df_m_prog, v_prog)
        
        # Metric Sesuai Skrip Inti (SO)
        total_t, sudah_t = len(df_u), df_u['STATUS'].sum()
        belum_t = total_t - sudah_t
        persen_t = (sudah_t / total_t) if total_t > 0 else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Toko", total_t)
        c2.metric("Sudah SO", sudah_t, f"{persen_t:.1%}")
        c3.metric("Belum SO", belum_t, f"-{belum_t}", delta_color="inverse")
        st.write("---")
        
        # Progres Tabel Sesuai Skrip Inti (SO)
        st.write("### 📊 Progres SO PER AM (Urutan Terendah di Atas)")
        am_sum = df_u.groupby('AM').agg(Target_Toko_SO=('KDTOKO', 'count'), Sudah_SO=('STATUS', 'sum')).reset_index()
        am_sum['Belum_SO'] = am_sum['Target_Toko_SO'] - am_sum['Sudah_SO']
        am_sum['Progres_Val'] = (am_sum['Sudah_SO'] / am_sum['Target_Toko_SO']).round(2)
        st.dataframe(am_sum.sort_values('Progres_Val'), column_config={"Target_Toko_SO":"Target Toko SO", "Sudah_SO":"Sudah SO", "Belum_SO":"Belum SO", "Progres_Val": st.column_config.ProgressColumn("Progres", format="%.2f", min_value=0, max_value=1)}, hide_index=True, use_container_width=True)

        st.write("### 📊 Progres SO PER AS (Urutan Terendah di Atas)")
        as_sum = df_u.groupby('AS').agg(Target_Toko_SO=('KDTOKO', 'count'), Sudah_SO=('STATUS', 'sum')).reset_index()
        as_sum['Belum_SO'] = as_sum['Target_Toko_SO'] - as_sum['Sudah_SO']
        as_sum['Progres_Val'] = (as_sum['Sudah_SO'] / as_sum['Target_Toko_SO']).round(2)
        st.dataframe(as_sum.sort_values('Progres_Val'), column_config={"Target_Toko_SO":"Target Toko SO", "Sudah_SO":"Sudah SO", "Belum_SO":"Belum SO", "Progres_Val": st.column_config.ProgressColumn("Progres", format="%.2f", min_value=0, max_value=1)}, hide_index=True, use_container_width=True)

        st.write("---")
        df_belum_all = df_u[df_u['STATUS'] == 0].copy()
        
        # Expander Sesuai Skrip Inti (SO)
        with st.expander("🔍 Detail Toko Belum SO Per AM"):
            if not df_belum_all.empty:
                sel_am_det = st.selectbox("Pilih Area Manager (AM):", options=sorted(df_belum_all['AM'].unique()), key="sel_am_det")
                df_det_am = df_belum_all[df_belum_all['AM'] == sel_am_det][['KDTOKO', 'NAMA TOKO']]
                df_det_am.columns = ['Kode', 'Nama']
                st.dataframe(df_det_am, hide_index=True, use_container_width=True)
            else: st.success("Semua toko sudah SO!")

        with st.expander("🔍 Detail Toko Belum SO Per AS"):
            if not df_belum_all.empty:
                sel_as_det = st.selectbox("Pilih AS:", options=sorted(df_belum_all['AS'].unique()), key="sel_as_det")
                df_det_as = df_belum_all[df_belum_all['AS'] == sel_as_det][['KDTOKO', 'NAMA TOKO']]
                df_det_as.columns = ['Kode', 'Nama']
                st.dataframe(df_det_as, hide_index=True, use_container_width=True)
            else: st.success("Semua toko sudah SO!")

    st.write("---")
    tab_login, tab_daftar = st.tabs(["🔐 Masuk", "📝 Daftar Akun"])
    with tab_login:
        l_nik = st.text_input("NIK:", max_chars=10, key="l_nik")
        l_pw = st.text_input("Password:", type="password", key="l_pw")
        if st.button("LOG IN", type="primary", use_container_width=True):
            db = get_user_db_safe() # Penguatan Login
            if db and l_nik in db and db[l_nik] == l_pw:
                st.session_state.user_nik, st.session_state.page = l_nik, "USER_INPUT"; st.rerun()
            elif db is None: st.error("Database user error. Mohon klik login kembali.")
            else: st.error("NIK/Password salah!")
        st.markdown(f'<a href="https://wa.me/6287725860048" target="_blank" style="text-decoration:none;"><button style="width:100%; background:transparent; color:white; border:1px solid white; border-radius:5px; cursor:pointer; padding:5px;">❓ Lupa Password? Hubungi Admin</button></a>', unsafe_allow_html=True)
    
    with tab_daftar:
        d_nik = st.text_input("NIK Baru:", max_chars=10, key="d_nik")
        d_pw = st.text_input("Password Baru:", type="password", key="d_pw")
        d_cpw = st.text_input("Konfirmasi Password:", type="password", key="d_cpw")
        if st.button("DAFTAR", use_container_width=True):
            if d_nik and d_pw == d_cpw:
                db_r = get_user_db_safe()
                if db_r and d_nik in db_r: st.warning("NIK sudah ada.")
                else:
                    db_r[d_nik] = d_pw
                    if update_user_db(db_r): st.success("Pendaftaran Berhasil!")
            else: st.error("Data tidak valid.")
    
    if st.button("🛡️ Admin Login", use_container_width=True): st.session_state.page = "ADMIN_AUTH"; st.rerun()

elif st.session_state.page == "ADMIN_AUTH":
    pw_adm = st.text_input("Password Admin:", type="password")
    if st.button("Masuk Admin"):
        if pw_adm == "icnkl034": st.cache_data.clear(); st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Salah!")
    if st.button("Kembali"): st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 4. ADMIN PANEL (RESTORASI HAPUS MASTER & PERMINTAAN 3, 5)
# =================================================================
elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Admin Panel")
    tab_rek, tab_mas, tab_usr, tab_res = st.tabs(["📊 Rekap", "📤 Master", "👤 Kelola User", "🔥 Reset & MT"])
    
    with tab_rek:
        df_m_rek, v_aktif_rek = get_master_data()
        # PERMINTAAN 3: Pilih bulan rekap
        st.info(f"Seri Data Saat Ini: {v_aktif_rek}")
        target_v = st.text_input("Pilih Periode Rekap (MM-YYYY):", value=v_aktif_rek)
        
        if st.button("📥 Download Full Master Rekap (Item Minus Only)", use_container_width=True):
            with st.spinner("Menggabungkan data..."):
                res_rek = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
                filtered_rek = [f for f in res_rek.get('resources', []) if f"v{target_v}" in f['public_id']]
                combined_in = pd.DataFrame(columns=['KDTOKO', 'PRDCD', 'KETERANGAN'])
                if filtered_rek:
                    inputs_list = []
                    for f in filtered_rek:
                        try:
                            df_t = pd.read_excel(f"{f['secure_url']}?t={int(time.time())}")
                            df_t.columns = [str(c).upper().strip() for c in df_t.columns]
                            inputs_list.append(df_t[['KDTOKO', 'PRDCD', 'KETERANGAN']])
                        except: pass
                    if inputs_list: combined_in = pd.concat(inputs_list, ignore_index=True).drop_duplicates(subset=['KDTOKO', 'PRDCD'])
                
                # PERMINTAAN 5: Rekap Full Master, hanya item minus
                if not df_m_rek.empty:
                    df_minus_master = df_m_rek[df_m_rek['RP SO NOW'] < 0].copy()
                    m_cols = list(df_minus_master.columns)
                    df_m_mrg = df_minus_master.drop(columns=['KETERANGAN']) if 'KETERANGAN' in df_minus_master.columns else df_minus_master.copy()
                    final_rekap = df_m_mrg.merge(combined_in, on=['KDTOKO', 'PRDCD'], how='left').fillna("")
                    final_rekap = final_rekap[m_cols if 'KETERANGAN' in m_cols else m_cols + ['KETERANGAN']]
                    
                    out_rek = io.BytesIO()
                    with pd.ExcelWriter(out_rek) as w: final_rekap.to_excel(w, index=False)
                    st.download_button("📥 Klik Download", out_rek.getvalue(), f"Full_Rekap_Minus_{target_v}.xlsx")

    with tab_mas:
        # CEK MASTER AKTIF
        master_status = False
        try:
            cloudinary.api.resource(MASTER_PATH, resource_type="raw"); master_status = True
        except: pass

        f_up = st.file_uploader("Upload Master Tambahan", type=["xlsx"])
        if f_up and st.button("🚀 Update Master"):
            old_df, _ = get_master_data()
            new_df = pd.read_excel(f_up)
            new_df.columns = [str(c).strip().upper() for c in new_df.columns]
            final_master = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(subset=['KDTOKO', 'PRDCD'], keep='last')
            if 'KETERANGAN' in final_master.columns: final_master['KETERANGAN'] = ""
            buf = io.BytesIO()
            with pd.ExcelWriter(buf) as w: final_master.to_excel(w, index=False)
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
            
            # Pesan Dinamis
            if master_status: st.success("✅ Master sukses diperbarui")
            else: st.success("✅ Master baru berhasil diupload")
            st.cache_data.clear(); time.sleep(1); st.rerun()

        st.divider()
        # RESTORASI FITUR HAPUS MASTER AKTIF (SKRIP INTI)
        st.subheader("🗑️ Hapus Master Aktif")
        with st.container(border=True):
            opsi_h_input = st.checkbox("Ikut hapus seluruh hasil input user berjalan?", value=False)
            konfirmasi_del = st.text_input("Ketik 'HAPUS' untuk menghapus Master Aktif:")
            if st.button("🔥 Eksekusi Hapus Master", type="primary"):
                if konfirmasi_del == "HAPUS":
                    cloudinary.uploader.destroy(MASTER_PATH, resource_type="raw")
                    if opsi_h_input:
                        res_all = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
                        pids_all = [f['public_id'] for f in res_all.get('resources', [])]
                        if pids_all: cloudinary.api.delete_resources(pids_all, resource_type="raw")
                    st.cache_data.clear(); st.success("Master Terhapus!"); time.sleep(1); st.rerun()

    with tab_usr:
        st.subheader("Reset Password User")
        nik_man = st.text_input("Ketik NIK User:"); db_u = get_user_db_safe()
        if nik_man and db_u and nik_man in db_u:
            p_new = st.text_input("Password Baru:", type="password")
            if st.button("Update Sekarang"):
                db_u[nik_man] = p_new
                if update_user_db(db_u): st.success("Update Berhasil!"); st.rerun()

    with tab_res:
        # PERMINTAAN 4: Toggle Maintenance Mode
        st.subheader("🛠️ Maintenance Mode")
        is_mt_now = get_maintenance_status()
        if is_mt_now:
            st.warning("Web Terkunci (Maintenance)")
            if st.button("🔴 MATIKAN MAINTENANCE"):
                if set_maintenance_status(False): st.success("Web Dibuka!"); time.sleep(1); st.rerun()
        else:
            st.success("Web Terbuka (Online)")
            if st.button("🟢 AKTIFKAN MAINTENANCE"):
                if set_maintenance_status(True): st.success("Web Dikunci!"); time.sleep(1); st.rerun()
        
        st.divider()
        # RESTORASI HAPUS HASIL INPUT (SKRIP INTI)
        st.subheader("🔥 Reset Hasil Input")
        if st.button("HAPUS SEMUA HASIL INPUT TANPA HAPUS MASTER", type="primary"):
            res_res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
            pids_res = [f['public_id'] for f in res_res.get('resources', [])]
            if pids_res: cloudinary.api.delete_resources(pids_res, resource_type="raw")
            st.cache_data.clear(); st.success("Dibersihkan!"); time.sleep(1); st.rerun()

    if st.button("Keluar Admin"): 
        st.cache_data.clear(); st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 5. USER INPUT (NK/NL, REFRESH, ANIMASI & KOLOM BARU)
# =================================================================
elif st.session_state.page == "USER_INPUT":
    st.title("📋 Input Penjelasan Pareto")
    df_m_in, v_m_in = get_master_data()
    if not df_m_in.empty:
        s_am = st.selectbox("1. PILIH AM:", sorted(df_m_in['AM'].unique()))
        df_am = df_m_in[df_m_in['AM'] == s_am]
        s_toko = st.selectbox("2. PILIH NAMA TOKO:", sorted(df_am['NAMA TOKO'].unique()))
        df_sel = df_am[df_am['NAMA TOKO'] == s_toko]
        
        v_kd, v_as = str(df_sel['KDTOKO'].iloc[0]), str(df_sel['AS'].iloc[0])
        
        # RESTORASI HEADER DENGAN REFRESH (SKRIP INTI)
        c1_u, c2_u, c3_u = st.columns([2, 2, 1])
        c1_u.metric("KDTOKO:", v_kd)
        c2_u.metric("AS:", v_as)
        with c3_u:
            if st.button("🔄 Refresh Data"): st.cache_data.clear(); st.rerun()

        # Sinkronisasi Real-time (Skrip Inti)
        data_final = df_sel.copy()
        data_final['PRDCD'] = data_final['PRDCD'].astype(str).str.strip()
        existing_res = get_existing_result(v_kd, v_m_in)
        if existing_res is not None:
            if validate_file_exists_in_cloudinary(v_kd, v_m_in):
                cloud_dat = existing_res[['PRDCD', 'KETERANGAN']].copy()
                cloud_dat['PRDCD'] = cloud_dat['PRDCD'].astype(str).str.strip()
                if 'KETERANGAN' in data_final.columns: data_final = data_final.drop(columns=['KETERANGAN'])
                data_final = data_final.merge(cloud_dat.drop_duplicates(subset=['PRDCD']), on='PRDCD', how='left')
        
        # Format Kolom Numerik Ribuan (PERMINTAAN 1)
        data_final['KETERANGAN'] = data_final['KETERANGAN'].fillna("").astype(str).replace(['nan','NaN','None'], '')
        so_cols = ['QTY SO LALU', 'RP SO LALU', 'QTY SO NOW', 'RP SO NOW']
        for c in so_cols: 
            data_final[c] = pd.to_numeric(data_final[c], errors='coerce').fillna(0)

        # PEMISAHAN NK & NL (Permintaan 1)
        df_nk = data_final[data_final['RP SO NOW'] < 0].copy()
        df_nl = data_final[data_final['RP SO NOW'] >= 0].copy()

        conf_view = {"PRDCD": st.column_config.TextColumn("PRDCD"), "DESC": st.column_config.TextColumn("DESC"),
                     "QTY SO LALU": st.column_config.NumberColumn("QTY LALU", format="%,d"), "RP SO LALU": st.column_config.NumberColumn("RP LALU", format="%,d"),
                     "QTY SO NOW": st.column_config.NumberColumn("QTY NOW", format="%,d"), "RP SO NOW": st.column_config.NumberColumn("RP NOW", format="%,d")}

        st.markdown('<div class="nk-label"><b>🟥 20 item minus (NK) terbesar harap isi keterangan!</b></div>', unsafe_allow_html=True)
        ed_nk = st.data_editor(df_nk[['PRDCD', 'DESC', 'QTY SO LALU', 'RP SO LALU', 'QTY SO NOW', 'RP SO NOW', 'KETERANGAN']], 
                               column_config={**conf_view, "KETERANGAN": st.column_config.TextColumn("KETERANGAN (Wajib Isi)", required=True)}, 
                               hide_index=True, use_container_width=True, key=f"ed_nk_{v_kd}")

        st.markdown('<div class="nl-label"><b>🟩 20 item plus terbesar (NL) hanya sebagai penampil saja!</b></div>', unsafe_allow_html=True)
        st.dataframe(df_nl[['PRDCD', 'DESC', 'QTY SO LALU', 'RP SO LALU', 'QTY SO NOW', 'RP SO NOW']], column_config=conf_view, hide_index=True, use_container_width=True)

        if st.button("🚀 Simpan Hasil Input", type="primary", use_container_width=True):
            if ed_nk['KETERANGAN'].apply(lambda x: str(x).strip() == "").any():
                st.error("⚠️ Mohon isi seluruh kolom keterangan NK!")
            else:
                df_nk['KETERANGAN'] = ed_nk['KETERANGAN'].values
                df_nl['KETERANGAN'] = "ini item nl!"
                save_df = pd.concat([df_nk, df_nl], ignore_index=True)
                orig_m_cols = [c for c in df_m_in.columns if c != 'KETERANGAN']
                buf_s = io.BytesIO()
                with pd.ExcelWriter(buf_s) as w: save_df[orig_m_cols + ['KETERANGAN']].to_excel(w, index=False)
                cloudinary.uploader.upload(buf_s.getvalue(), resource_type="raw", public_id=f"pareto_nkl/hasil/Hasil_{v_kd}_v{v_m_in}.xlsx", overwrite=True, invalidate=True)
                # ANIMASI & PESAN SUKSES 2 DETIK (PERMINTAAN 3)
                st.balloons(); st.success("✅ Input keterangan sukses!"); time.sleep(2); st.cache_data.clear(); st.rerun()

    if st.button("Log Out"): st.cache_data.clear(); st.session_state.page = "HOME"; st.rerun()
