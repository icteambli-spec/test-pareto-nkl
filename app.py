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
# 1. KONFIGURASI & CLOUDINARY
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

# Konfigurasi API ic@bli
PHP_API_URL = "https://inventorycontrolbali.my.id/api/paretoNkl_sync_pull.php" # Endpoint Pull Data
PHP_API_KEY = "ic@bli2601"

# Custom CSS Glassmorphism (Skrip Inti)
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(0,0,0,0.8), rgba(0,0,0,0.8)), 
                    url("https://res.cloudinary.com/dydpottpm/image/upload/v1771858607/Prisoner_With_Sad_Face_Hold_Cage_In_Silence_Situation_Prison_Clipart_Arrested_Cage_PNG_and_Vector_with_Transparent_Background_for_Free_Download_xhpf5r.jpg");
        background-size: cover; background-attachment: fixed;
    }
    h1, h2, h3, p, span, label, .stTabs [data-baseweb="tab"] { 
        color: white !important; 
        text-shadow: 1px 1px 2px black; 
    }
    div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] { 
        background-color: rgba(255,255,255,0.05); 
        border-radius: 10px; padding: 10px; 
    }
    [data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    .nk-label { background-color: rgba(255, 75, 75, 0.2); padding: 10px; border-radius: 5px; border-left: 5px solid #ff4b4b; margin-bottom: 10px; }
    .nl-label { background-color: rgba(46, 204, 113, 0.2); padding: 10px; border-radius: 5px; border-left: 5px solid #2ecc71; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

USER_DB = "pareto_nkl/config/test_users_pareto_nkl.json"
MASTER_PATH = "pareto_nkl/test_master_pareto_nkl.xlsx"

# =================================================================
# 2. FUNGSI CORE & FIX LOGIN (SKRIP INTI)
# =================================================================

def clear_all_caches():
    st.cache_data.clear()
    keys_to_delete = [k for k in st.session_state.keys() if any(x in k for x in ['ed_', 'result', 'data_toko', 'hash', 'user_db'])]
    for key in keys_to_delete:
        del st.session_state[key]

def get_user_db_safe():
    """FIX: Database User Error Handler dengan Retry Logic"""
    if 'user_db_cache' in st.session_state:
        return st.session_state.user_db_cache
    
    url_user = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{USER_DB}?t={int(time.time())}"
    for i in range(3):
        try:
            resp = requests.get(url_user, timeout=10)
            if resp.status_code == 200:
                db = resp.json()
                st.session_state.user_db_cache = db
                return db
        except:
            time.sleep(1)
    return None

def clean_numeric(val):
    if pd.isna(val) or val == "": return 0.0
    s = str(val).replace(',', '').replace(' ', '')
    if '(' in s and ')' in s:
        s = '-' + s.replace('(', '').replace(')', '')
    try: return float(s)
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
        for col in df.columns:
            if col in ['QTY', 'RUPIAH']: df[col] = df[col].apply(clean_numeric)
            else: df[col] = df[col].fillna("")
        if 'KETERANGAN' in df.columns: df['KETERANGAN'] = ""
        return df, v
    except: return pd.DataFrame(), datetime.now().strftime("%m-%Y")

def get_existing_result(toko_code, version):
    try:
        p_id = f"pareto_nkl/hasil/Hasil_{toko_code}_v{version}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{p_id}?t={int(time.time())}"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            df_res = pd.read_excel(io.BytesIO(resp.content))
            df_res.columns = [str(c).strip().upper() for c in df_res.columns]
            return df_res
        return None
    except: return None

def validate_file_exists_in_cloudinary(toko_code, version):
    try:
        p_id = f"pareto_nkl/hasil/Hasil_{toko_code}_v{version}.xlsx"
        cloudinary.api.resource(p_id, resource_type="raw")
        return True
    except: return False

def update_user_db(new_db):
    try:
        cloudinary.uploader.upload(io.BytesIO(json.dumps(new_db).encode()), resource_type="raw", public_id=USER_DB, overwrite=True, invalidate=True)
        clear_all_caches()
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
            if p_id.endswith(suffix): finished_stores.append(p_id.replace("Hasil_", "").replace(suffix, ""))
        df_u = df_m.drop_duplicates(subset=['KDTOKO']).copy()
        df_u['STATUS'] = df_u['KDTOKO'].apply(lambda x: 1 if x in finished_stores else 0)
        return df_u, finished_stores
    except: return pd.DataFrame(), []

# =================================================================
# 3. ROUTING & HOME (PROGRES SO AM/AS)
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "HOME"

if st.session_state.page == "HOME":
    st.title("📑 Sistem Penjelasan Pareto NKL")
    df_m_prog, v_prog = get_master_data()
    if not df_m_prog.empty:
        df_u, finished_list = get_progress_data(df_m_prog, v_prog)
        total_t, sudah_t = len(df_u), df_u['STATUS'].sum()
        belum_t = total_t - sudah_t
        persen_t = (sudah_t / total_t) if total_t > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Toko", total_t)
        c2.metric("Sudah SO", sudah_t, f"{persen_t:.1%}")
        c3.metric("Belum SO", belum_t, f"-{belum_t}", delta_color="inverse")
        
        st.write("---")
        st.write("### 📊 Progres SO PER AM (Urutan Terendah di Atas)")
        am_sum = df_u.groupby('AM').agg(Target_Toko_SO=('KDTOKO', 'count'), Sudah_SO=('STATUS', 'sum')).reset_index()
        am_sum['Belum_SO'] = am_sum['Target_Toko_SO'] - am_sum['Sudah_SO']
        am_sum['Progres_Val'] = (am_sum['Sudah_SO'] / am_sum['Target_Toko_SO']).round(2)
        st.dataframe(am_sum.sort_values('Progres_Val'), column_config={"Progres_Val": st.column_config.ProgressColumn("Progres", format="%.2f", min_value=0, max_value=1)}, hide_index=True, use_container_width=True)

        st.write("### 📊 Progres SO PER AS (Urutan Terendah di Atas)")
        as_sum = df_u.groupby('AS').agg(Target_Toko_SO=('KDTOKO', 'count'), Sudah_SO=('STATUS', 'sum')).reset_index()
        as_sum['Belum_SO'] = as_sum['Target_Toko_SO'] - as_sum['Sudah_SO']
        as_sum['Progres_Val'] = (as_sum['Sudah_SO'] / as_sum['Target_Toko_SO']).round(2)
        st.dataframe(as_sum.sort_values('Progres_Val'), column_config={"Progres_Val": st.column_config.ProgressColumn("Progres", format="%.2f", min_value=0, max_value=1)}, hide_index=True, use_container_width=True)

        st.write("---")
        df_belum_all = df_u[df_u['STATUS'] == 0].copy()
        with st.expander("🔍 Detail Toko Belum SO Per AM"):
            if not df_belum_all.empty:
                sel_am_det = st.selectbox("Pilih AM:", options=sorted(df_belum_all['AM'].unique()), key="sel_am_det")
                st.dataframe(df_belum_all[df_belum_all['AM'] == sel_am_det][['KDTOKO', 'NAMA TOKO']].rename(columns={'KDTOKO':'Kode','NAMA TOKO':'Nama'}), hide_index=True, use_container_width=True)
        with st.expander("🔍 Detail Toko Belum SO Per AS"):
            if not df_belum_all.empty:
                sel_as_det = st.selectbox("Pilih AS:", options=sorted(df_belum_all['AS'].unique()), key="sel_as_det")
                st.dataframe(df_belum_all[df_belum_all['AS'] == sel_as_det][['KDTOKO', 'NAMA TOKO']].rename(columns={'KDTOKO':'Kode','NAMA TOKO':'Nama'}), hide_index=True, use_container_width=True)

    st.write("---")
    tab_login, tab_daftar = st.tabs(["🔐 Masuk", "📝 Daftar Akun"])
    with tab_login:
        l_nik = st.text_input("NIK:", max_chars=10, key="l_nik")
        l_pw = st.text_input("Password:", type="password", key="l_pw")
        if st.button("LOG IN", type="primary", use_container_width=True):
            db_login = get_user_db_safe()
            if db_login and l_nik in db_login and db_login[l_nik] == l_pw:
                clear_all_caches(); st.session_state.user_nik, st.session_state.page = l_nik, "USER_INPUT"; st.rerun()
            elif db_login is None: st.error("Database user error. Klik lagi.")
            else: st.error("NIK/Password salah!")
        st.markdown(f'<a href="https://wa.me/6287725860048" target="_blank" style="text-decoration:none;"><button style="width:100%; background:transparent; color:white; border:1px solid white; border-radius:5px; cursor:pointer; padding:5px;">❓ Lupa Password? Hubungi Admin</button></a>', unsafe_allow_html=True)
    
    with tab_daftar:
        d_nik = st.text_input("NIK Baru:", max_chars=10, key="d_nik")
        d_pw = st.text_input("Password Baru:", type="password", key="d_pw")
        d_cpw = st.text_input("Konfirmasi Password:", type="password", key="d_cpw")
        if st.button("DAFTAR", use_container_width=True):
            if d_nik and d_pw == d_cpw:
                db_reg = get_user_db_safe()
                if db_reg and d_nik in db_reg: st.warning("NIK sudah ada.")
                else:
                    db_reg[d_nik] = d_pw
                    if update_user_db(db_reg): st.success("Pendaftaran Berhasil!")
            else: st.error("Data tidak valid.")
    if st.button("🛡️ Admin Login", use_container_width=True): st.session_state.page = "ADMIN_AUTH"; st.rerun()

# =================================================================
# 4. ADMIN PANEL (FULL MASTER REKAP & 2-WAY UPDATE)
# =================================================================
elif st.session_state.page == "ADMIN_AUTH":
    pw_adm = st.text_input("Password Admin:", type="password")
    if st.button("Masuk Admin"):
        if pw_adm == "icnkl034": clear_all_caches(); st.session_state.page = "ADMIN_PANEL"; st.rerun()
        else: st.error("Password Admin Salah!")
    if st.button("Kembali"): st.session_state.page = "HOME"; st.rerun()

elif st.session_state.page == "ADMIN_PANEL":
    st.title("🛡️ Admin Panel")
    tab_rek, tab_mas, tab_usr, tab_res = st.tabs(["📊 Rekap", "📤 Master", "👤 Kelola User", "🔥 Reset"])
    
    with tab_rek:
        df_m_rek, v_aktif_rek = get_master_data()
        target_v = st.text_input("Tarik Data Seri (MM-YYYY):", value=v_aktif_rek)
        if st.button("📥 Download Full Master Rekap", use_container_width=True):
            with st.spinner("Menggabungkan data..."):
                res_rek = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
                filtered_rek = [f for f in res_rek.get('resources', []) if f"v{target_v}" in f['public_id']]
                combined_in = pd.DataFrame(columns=['KDTOKO', 'PLU', 'KETERANGAN'])
                if filtered_rek:
                    inputs_rek = []
                    for f in filtered_rek:
                        try:
                            df_t = pd.read_excel(f"{f['secure_url']}?t={int(time.time())}")
                            df_t.columns = [str(c).upper().strip() for c in df_t.columns]
                            inputs_rek.append(df_t[['KDTOKO', 'PLU', 'KETERANGAN']])
                        except: pass
                    if inputs_rek: combined_in = pd.concat(inputs_rek, ignore_index=True).drop_duplicates(subset=['KDTOKO', 'PLU'])
                
                m_cols = list(df_m_rek.columns)
                df_m_mrg = df_m_rek.drop(columns=['KETERANGAN']) if 'KETERANGAN' in df_m_rek.columns else df_m_rek.copy()
                final_rekap = df_m_mrg.merge(combined_in, on=['KDTOKO', 'PLU'], how='left').fillna("")
                final_rekap = final_rekap[m_cols if 'KETERANGAN' in m_cols else m_cols + ['KETERANGAN']]
                out_rek = io.BytesIO()
                with pd.ExcelWriter(out_rek) as w: final_rekap.to_excel(w, index=False)
                st.download_button("📥 Klik Download", out_rek.getvalue(), f"Full_Rekap_{target_v}.xlsx")

    with tab_mas:
        st.subheader("Pilih Jalur Update Master")
        master_aktif_exists = False
        try:
            cloudinary.api.resource(MASTER_PATH, resource_type="raw")
            master_aktif_exists = True
        except: pass

        # JALUR 1: SYNC API (NEW)
        if st.button("🔄 Sinkronisasi Master dari Server PHP ic@bli", use_container_width=True):
            with st.spinner("Menghubungi Server ic@bli..."):
                try:
                    resp_api = requests.post(PHP_API_URL, data={"api_key": PHP_API_KEY}, timeout=30)
                    if resp_api.status_code == 200:
                        data_api = resp_api.json()
                        new_df_api = pd.DataFrame(data_api)
                        new_df_api.columns = [str(c).strip().upper() for c in new_df_api.columns]
                        
                        old_df_m, _ = get_master_data()
                        final_m = pd.concat([old_df_m, new_df_api], ignore_index=True).drop_duplicates(subset=['KDTOKO', 'PLU'], keep='last')
                        if 'KETERANGAN' in final_m.columns: final_m['KETERANGAN'] = ""
                        
                        buf_m = io.BytesIO()
                        with pd.ExcelWriter(buf_m) as w: final_m.to_excel(w, index=False)
                        cloudinary.uploader.upload(buf_m.getvalue(), resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
                        
                        if master_aktif_exists: st.success("✅ Master sukses diperbarui dari API")
                        else: st.success("✅ Master baru berhasil diupload dari API")
                        clear_all_caches(); time.sleep(2); st.rerun()
                    else: st.error(f"Gagal Sync API: Status {resp_api.status_code}")
                except Exception as e: st.error(f"⚠️ Koneksi ke Server PHP Gagal: {e}. Gunakan mode Upload Manual.")

        st.write("---")
        # JALUR 2: MANUAL UPLOAD (SKRIP INTI)
        f_up = st.file_uploader("Upload Master Tambahan Manual (.xlsx)", type=["xlsx"])
        if f_up and st.button("🚀 Update Master Manual"):
            old_df_m, _ = get_master_data()
            new_df_m = pd.read_excel(f_up)
            new_df_m.columns = [str(c).strip().upper() for c in new_df_m.columns]
            final_m = pd.concat([old_df_m, new_df_m], ignore_index=True).drop_duplicates(subset=['KDTOKO', 'PLU'], keep='last')
            if 'KETERANGAN' in final_m.columns: final_m['KETERANGAN'] = ""
            buf_m = io.BytesIO()
            with pd.ExcelWriter(buf_m) as w: final_m.to_excel(w, index=False)
            cloudinary.uploader.upload(buf_m.getvalue(), resource_type="raw", public_id=MASTER_PATH, overwrite=True, invalidate=True)
            if master_aktif_exists: st.success("✅ Master sukses diperbarui manual")
            else: st.success("✅ Master baru berhasil diupload manual")
            clear_all_caches(); time.sleep(2); st.rerun()

        st.divider()
        st.subheader("🗑️ Hapus Master Aktif")
        opsi_h = st.checkbox("Ikut hapus seluruh hasil input user?")
        if st.button("🔥 Eksekusi Hapus Master", type="primary"):
            cloudinary.uploader.destroy(MASTER_PATH, resource_type="raw")
            if opsi_h:
                res_del = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
                pids = [f['public_id'] for f in res_del.get('resources', [])]
                if pids: cloudinary.api.delete_resources(pids, resource_type="raw")
            clear_all_caches(); st.success("Master Terhapus!"); time.sleep(2); st.rerun()

    with tab_usr:
        nik_man = st.text_input("Ketik NIK User:")
        db_usr_adm = get_user_db_safe()
        if nik_man and db_usr_adm and nik_man in db_usr_adm:
            p_new = st.text_input("Password Baru:", type="password")
            if st.button("Update Sekarang"):
                db_usr_adm[nik_man] = p_new
                if update_user_db(db_usr_adm): st.success("Reset Password Sukses!"); time.sleep(2); st.rerun()

    with tab_res:
        if st.button("🔥 RESET HASIL INPUT", type="primary"):
            res_res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="pareto_nkl/hasil/")
            pids_res = [f['public_id'] for f in res_res.get('resources', [])]
            if pids_res: cloudinary.api.delete_resources(pids_res, resource_type="raw")
            clear_all_caches(); st.success("Bersih!"); time.sleep(2); st.rerun()

    if st.button("🚪 Logout Admin", use_container_width=True): clear_all_caches(); st.session_state.page = "HOME"; st.rerun()

# =================================================================
# 5. USER INPUT (TIERED NK/NL & ANIMATION)
# =================================================================
elif st.session_state.page == "USER_INPUT":
    st.title("📋 Input Pareto")
    df_m_in, v_master_in = get_master_data()
    if not df_m_in.empty:
        sel_am_in = st.selectbox("1. PILIH AM:", sorted(df_m_in['AM'].unique()))
        df_f_am_in = df_m_in[df_m_in['AM'] == sel_am_in]
        sel_nama_in = st.selectbox("2. PILIH NAMA TOKO:", sorted(df_f_am_in['NAMA TOKO'].unique()))
        df_sel_in = df_f_am_in[df_f_am_in['NAMA TOKO'] == sel_nama_in]
        
        if not df_sel_in.empty:
            v_kdtoko, v_as = str(df_sel_in['KDTOKO'].iloc[0]), str(df_sel_in['AS'].iloc[0])
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.metric("KDTOKO:", v_kdtoko); c2.metric("AS:", v_as)
            with c3:
                if st.button("🔄 Refresh", key="btn_ref"): clear_all_caches(); st.rerun()

            existing_res = get_existing_result(v_kdtoko, v_master_in)
            if existing_res is not None:
                if not validate_file_exists_in_cloudinary(v_kdtoko, v_master_in): existing_res = None
            
            data_final_in = df_sel_in.copy()
            data_final_in['PLU'] = data_final_in['PLU'].astype(str).str.strip()

            if existing_res is not None:
                cloud_dat = existing_res[['PLU', 'KETERANGAN']].copy()
                cloud_dat['PLU'] = cloud_dat['PLU'].astype(str).str.strip()
                if 'KETERANGAN' in data_final_in.columns: data_final_in = data_final_in.drop(columns=['KETERANGAN'])
                data_final_in = data_final_in.merge(cloud_dat.drop_duplicates(subset=['PLU']), on='PLU', how='left')
                st.success(f"✅ Sinkronisasi Berhasil: Isian lama Seri {v_master_in} dimuat.")
            else: data_final_in['KETERANGAN'] = ""

            for col in ['PLU', 'DESC', 'KETERANGAN']: data_final_in[col] = data_final_in[col].astype(str).replace(['nan','NaN','None'], '')
            for col in ['QTY', 'RUPIAH']: data_final_in[col] = pd.to_numeric(data_final_in[col], errors='coerce').fillna(0)

            df_nk = data_final_in[data_final_in['RUPIAH'] < 0].copy()
            df_nl = data_final_in[data_final_in['RUPIAH'] >= 0].copy()

            # PERBAIKAN FORMAT RIBUAN (%,d)
            config_user = {
                "PLU": st.column_config.TextColumn("PLU"),
                "DESC": st.column_config.TextColumn("DESC"),
                "QTY": st.column_config.NumberColumn("QTY", format="%,d"),
                "RUPIAH": st.column_config.NumberColumn("RUPIAH", format="%,d"),
            }

            st.markdown('<div class="nk-label"><b>🟥 20 item minus (NK) terbesar harap isi keterangan!</b></div>', unsafe_allow_html=True)
            d_hash = hashlib.md5(pd.util.hash_pandas_object(df_nk).values).hexdigest()
            edited_nk = st.data_editor(df_nk[['PLU', 'DESC', 'QTY', 'RUPIAH', 'KETERANGAN']], column_config={**config_user, "KETERANGAN": st.column_config.TextColumn("KETERANGAN (Wajib Isi)", required=True)}, hide_index=True, use_container_width=True, key=f"ed_nk_{v_kdtoko}_{d_hash}")

            st.markdown('<div class="nl-label"><b>🟩 20 item plus terbesar (NL) hanya sebagai penampil saja!</b></div>', unsafe_allow_html=True)
            st.dataframe(df_nl[['PLU', 'DESC', 'QTY', 'RUPIAH']], column_config=config_user, hide_index=True, use_container_width=True)

            if st.button("🚀 Simpan Hasil Input", type="primary", use_container_width=True):
                if edited_nk['KETERANGAN'].apply(lambda x: str(x).strip() == "").any():
                    st.error("⚠️ Semua kolom KETERANGAN item MINUS (NK) wajib diisi!")
                else:
                    df_nk['KETERANGAN'] = edited_nk['KETERANGAN'].values
                    df_nl['KETERANGAN'] = "ini item nl!"
                    combined_save = pd.concat([df_nk, df_nl], ignore_index=True)
                    orig_m_cols = [c for c in df_m_in.columns if c != 'KETERANGAN']
                    final_out = combined_save[orig_m_cols + ['KETERANGAN']]
                    buf_s = io.BytesIO()
                    with pd.ExcelWriter(buf_s) as w: final_out.to_excel(w, index=False)
                    cloudinary.uploader.upload(buf_s.getvalue(), resource_type="raw", public_id=f"pareto_nkl/hasil/Hasil_{v_kdtoko}_v{v_master_in}.xlsx", overwrite=True, invalidate=True)
                    st.balloons(); st.success("✅ Input keterangan sukses!"); time.sleep(2); clear_all_caches(); st.rerun()

    if st.button("Logout"): clear_all_caches(); st.session_state.page = "HOME"; st.rerun()

