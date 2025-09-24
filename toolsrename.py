import streamlit as st
import easyocr
from PIL import Image
import zipfile
import os
import io
import re
import tempfile
import pandas as pd
import numpy as np

# OCR Reader (biar ga bikin ulang tiap gambar)
reader = easyocr.Reader(['en'])

# ------------------- Ekstraksi -------------------
def extract_account_name(text):
    match = re.search(r'Account Name\s*[:\-]?\s*(.*)', text, re.IGNORECASE)
    if match:
        name_raw = match.group(1)
        name_clean = re.split(r'\n|Account Number', name_raw, flags=re.IGNORECASE)[0].strip()
        if re.search(r'\s+[A-Z]$', name_clean):
            name_clean = re.sub(r'\s+[A-Z]$', '', name_clean)
        final_name = re.sub(r'\s+', ' ', name_clean).title()
        return final_name
    return None

def extract_account_number_from_text(text):
    match = re.search(r'Account Number\s*[:\-]?\s*(\d{6,})', text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def extract_va(text):
    clean_text = text.replace("\n", " ").replace(":", " ").replace("-", " ")
    m = re.search(r'(virtual\s*account|no\s*va|va)\s*([0-9\s]{6,25})', clean_text, re.IGNORECASE)
    if m:
        digits = re.sub(r'\D', '', m.group(2))
        if len(digits) >= 6:
            return digits
    m2 = re.search(r'\b\d{8,20}\b', clean_text)
    return m2.group(0) if m2 else None

def sanitize_name(name):
    safe = re.sub(r'[\\/*?:"<>|]', '_', name).strip()
    safe = re.sub(r'\s+', '_', safe)
    return safe[:120]

# ------------------- UI -------------------
st.set_page_config(page_title="AUTORENAME TOOL BY WILD", page_icon="🪪", layout="centered")
st.title("🔥AUTORENAME TOOL BY WILD")
st.markdown("""
Selamat datang di **tool sakti mandraguna** buat rename file otomatis!  
👍Upload gambar/zip, pilih bank & mode, lalu tinggal klik — abis gitu tinggal nyantai aja, biar gue yang ngerjain.  
*(Web ini kadang suka halu — kalo salah tinggal upload ulang atau edit manual nanti kalo masih gabisa juga coba berdoa sambil colek wildan ya!.)*
""")
st.caption("👑 Dibuat oleh Wild — internal tool, kelas pake z KELAZ")

option = st.selectbox("🏦 Pilih bank lo:", ["OY", "BCA"])
if option == "OY":
    mode = st.selectbox("📌 Mau rename ke:", ["Nomor Rekening", "Nama Rekening"])
else:
    mode = "Virtual Account"
    st.info("🚨 BCA : Baru bisa virtual account doang, sabar ya bestie 🙏")

uploaded = st.file_uploader(
    "🎒 Taruh file lo di sini (jpg/png/zip). Bisa multiple.",
    type=["jpg", "jpeg", "png", "zip"],
    accept_multiple_files=True
)

def is_image_filename(fname):
    return fname.lower().endswith((".jpg", ".jpeg", ".png"))

# ------------------- Logic -------------------
if uploaded and st.button("⚡ Gaskeun Rename!"):
    tmpdir = tempfile.mkdtemp(prefix="autorename_")
    workdir = os.path.join(tmpdir, "work")
    os.makedirs(workdir, exist_ok=True)
    output_dir = os.path.join(tmpdir, "outputs")
    os.makedirs(output_dir, exist_ok=True)

    for f in uploaded:
        save_path = os.path.join(workdir, f.name)
        with open(save_path, "wb") as wf:
            wf.write(f.read())

        if f.name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(save_path, 'r') as z:
                    z.extractall(workdir)
                os.remove(save_path)
            except Exception as e:
                st.warning(f"Gagal extract {f.name}: {e}")

    image_paths = []
    for root, _, files in os.walk(workdir):
        for fn in files:
            if is_image_filename(fn):
                image_paths.append(os.path.join(root, fn))
    image_paths = sorted(image_paths)

    if len(image_paths) == 0:
        st.error("Ga ada gambar yang bisa diproses. Pastikan upload jpg/png atau zip isi gambar.")
    else:
        show_thumbnails = (len(uploaded) == 1 and is_image_filename(uploaded[0].name))

        st.success(f"Ketemu {len(image_paths)} gambar, mulai proses...")
        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []

        for idx, img_path in enumerate(image_paths, start=1):
            status_text.text(f"🚀 Lagi ngulik {os.path.basename(img_path)} ({idx}/{len(image_paths)})")
            try:
                img = Image.open(img_path).convert("RGB")
                results_ocr = reader.readtext(np.array(img), detail=0)
                text = "\n".join(results_ocr)

                extracted = None
                if option == "OY":
                    if mode == "Nomor Rekening":
                        extracted = extract_account_number_from_text(text)
                    elif mode == "Nama Rekening":
                        extracted = extract_account_name(text)
                else:  
                    extracted = extract_va(text)

                if extracted:
                    safe = sanitize_name(str(extracted))
                    ext = os.path.splitext(img_path)[1].lower()
                    candidate = f"{safe}{ext}"
                    counter = 1
                    while os.path.exists(os.path.join(output_dir, candidate)):
                        candidate = f"{safe}_{counter}{ext}"
                        counter += 1
                    new_path = os.path.join(output_dir, candidate)
                    img.save(new_path)

                    results.append({
                        "before": os.path.basename(img_path),
                        "after": candidate,
                        "status": "Renamed",
                        "orig_path": img_path,
                        "new_path": new_path,
                        "extracted": extracted
                    })
                else:
                    results.append({
                        "before": os.path.basename(img_path),
                        "after": "",
                        "status": "Failed",
                        "orig_path": img_path,
                        "new_path": "",
                        "extracted": ""
                    })
            except Exception as e:
                results.append({
                    "before": os.path.basename(img_path),
                    "after": "",
                    "status": "Failed",
                    "orig_path": img_path,
                    "new_path": "",
                    "extracted": ""
                })
            progress_bar.progress(idx / len(image_paths))

        status_text.text("🎉 Semua file udah diproses. Cek tabel di bawah ya.")

        if show_thumbnails:
            st.subheader("🔎 Preview singkat (Before → After)")
            for r in results:
                cols = st.columns([1, 3])
                with cols[0]:
                    try:
                        img = Image.open(r["orig_path"])
                        st.image(img, width=160)
                    except:
                        st.write("No preview")
                with cols[1]:
                    st.markdown(f"**{r['before']}** → **{r['after'] or '*NOT FOUND*'}**")
                    st.write(f"Status: `{r['status']}`")
                    if r['extracted']:
                        st.write(f"Extracted: `{r['extracted']}`")

        df = pd.DataFrame([{"Before": r["before"], "After": r["after"], "Status": r["status"]} for r in results])
        st.subheader("📋 Ringkasan hasil")
        st.dataframe(df, use_container_width=True)

        renamed_files = [r["new_path"] for r in results if r["status"] == "Renamed"]
        if renamed_files:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                for p in renamed_files:
                    zf.write(p, arcname=os.path.basename(p))
            zip_buf.seek(0)
            st.download_button("📦 Cekrek! Download hasil ZIP", zip_buf, file_name="renamed_output.zip")
        else:
            st.info("Ga ada file yang berhasil di-rename. Coba upload ulang atau cek kualitas gambar / mode.")

        failed = [r["before"] for r in results if r["status"] == "Failed"]
        if failed:
            st.warning(f"Ada {len(failed)} file gagal diproses. Contoh: {failed[:5]}")
