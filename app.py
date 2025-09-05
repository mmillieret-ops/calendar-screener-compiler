import io
import os
import re
from typing import Dict, List

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Calendar + Screener Compiler", page_icon="🧩", layout="wide")
st.title("🧩 Calendar + Screener Compiler")
st.write("Upload your **Calendar** and **Screener** files to generate a clean, merged Excel for your study.")

with st.expander("What this app does", expanded=False):
    st.markdown(
        "- Auto-detects **calendar** (or **calender**) and **screener** by filename\n"
        "- Maps headers robustly and merges on **EMAIL** (case-insensitive)\n"
        "- Removes linking fields from the final output\n"
        "- Produces: `Compiled Study Data - <project>.xlsx`"
    )

def coalesce_columns(df: pd.DataFrame, targets: Dict[str, List[str]]) -> pd.DataFrame:
    out = df.copy()
    existing_lower = {str(c).lower(): c for c in out.columns}
    for target, candidates in targets.items():
        found = None
        for cand in candidates:
            ckey = cand.lower()
            if ckey in existing_lower:
                found = existing_lower[ckey]
                break
        if not found:
            for c in out.columns:
                for cand in candidates:
                    if cand.lower() in str(c).lower():
                        found = c
                        break
                if found:
                    break
        if found:
            if found != target:
                out = out.rename(columns={found: target})
        else:
            out[target] = pd.NA
    return out

def normalize_text(s):
    if pd.isna(s):
        return s
    return str(s).strip()

def detect_roles(names: List[str]):
    calendar = next((n for n in names if ("calendar" in n.lower() or "calender" in n.lower())), None)
    screener = next((n for n in names if "screener" in n.lower()), None)
    return calendar, screener

def best_project_name(name: str) -> str:
    stem = os.path.splitext(os.path.basename(name))[0]
    stem = re.sub(r"(?i)\\bcalendar\\b|\\bcalender\\b|\\bscreener\\b|\\bcopy\\b", "", stem)
    stem = re.sub(r"\\s+", " ", stem).strip(" -_")
    return stem or "Project"

st.subheader("1) Upload files")
uploads = st.file_uploader(
    "Upload BOTH files (calendar & screener) — Excel (.xlsx/.xls) or CSV",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True
)

if uploads:
    uploaded_names = [u.name for u in uploads]
    cal_guess, scr_guess = detect_roles(uploaded_names)

    col1, col2 = st.columns(2)
    with col1:
        calendar_file = st.selectbox(
            "Select the Calendar file",
            ["-- choose --"] + uploaded_names,
            index=(uploaded_names.index(cal_guess) + 1) if cal_guess in uploaded_names else 0
        )
    with col2:
        screener_file = st.selectbox(
            "Select the Screener file",
            ["-- choose --"] + uploaded_names,
            index=(uploaded_names.index(scr_guess) + 1) if scr_guess in uploaded_names else 0
        )

    proceed = calendar_file != "-- choose --" and screener_file != "-- choose --"
else:
    proceed = False

def load_any(upload):
    name = upload.name.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(upload)
    elif name.endswith(".csv"):
        return pd.read_csv(upload)
    else:
        raise ValueError(f"Unsupported file type for {upload.name}. Use .xlsx, .xls, or .csv")

if proceed:
    files_map = {u.name: u for u in uploads}
    cal_up = files_map.get(calendar_file)
    scr_up = files_map.get(screener_file)

    try:
        cal_df = load_any(cal_up)
        scr_df = load_any(scr_up)
    except Exception as e:
        st.error(f"Failed to read files: {e}")
        st.stop()

    cal_df.columns = [str(c).strip() for c in cal_df.columns]
    scr_df.columns = [str(c).strip() for c in scr_df.columns]

    st.subheader("2) Preview detected columns")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Calendar columns**")
        st.write(list(cal_df.columns))
    with c2:
        st.markdown("**Screener columns**")
        st.write(list(scr_df.columns))

    st.subheader("3) Compile")
    with st.spinner("Compiling..."):
        cal_targets = {
            "User name": ["User name", "User Name", "Tester Name", "Tester"],
            "EMAIL": ["EMAIL", "Email", "Tester Email", "Participant Email"],
            "Start Time": ["Start Time", "Start Time (", "StartTime"],
            "End Time": ["End Time", "End Time (", "EndTime"],
            "Task Link": ["Task Link", "Task URL", "TaskLink"],
            "Moderator Link": ["Moderator Link", "Moderator URL", "ModeratorLink"],
            "Observers Public Link": ["Observers Public Link", "Observers Link", "Observer Link", "Public Observer Link"],
        }
        cal_std = coalesce_columns(cal_df, cal_targets)
        keep_calendar = ["User name", "EMAIL", "Start Time", "End Time", "Task Link", "Moderator Link", "Observers Public Link"]
        cal_std = cal_std[keep_calendar]

        scr_targets = {
            "TESTER": ["TESTER", "Tester", "User name", "User Name", "Tester Name"],
            "EMAIL": ["EMAIL", "Email"],
            "DATE": ["DATE", "Date", "Submission Date", "Created At"],
            "STATUS": ["STATUS", "Status"],
            "ADMIN RATING": ["ADMIN RATING", "Admin Rating"],
            "CLIENT RATING": ["CLIENT RATING", "Client Rating"],
        }
        scr_std = coalesce_columns(scr_df, scr_targets)

        exclude = ["TESTER", "EMAIL", "DATE", "STATUS", "ADMIN RATING", "CLIENT RATING"]
        scr_answers_cols = [c for c in scr_std.columns if c not in exclude]
        scr_answers = scr_std[scr_answers_cols].copy()

        cal_std["EMAIL_key"] = cal_std["EMAIL"].astype(str).str.strip().str.lower()
        scr_std["EMAIL_key"] = scr_std["EMAIL"].astype(str).str.strip().str.lower()

        merged = pd.merge(cal_std, pd.concat([scr_std[["EMAIL_key"]], scr_answers], axis=1),
                          on="EMAIL_key", how="inner")

        merged = merged.drop(columns=["EMAIL_key"], errors="ignore")
        if "EMAIL" in merged.columns:
            merged = merged.drop(columns=["EMAIL"])

        merged["User name"] = merged["User name"].apply(normalize_text)
        merged = merged.drop_duplicates(subset=["User name", "Start Time"], keep="first")

        head = ["User name", "Start Time", "End Time", "Task Link", "Moderator Link", "Observers Public Link"]
        tail = [c for c in merged.columns if c not in head]
        merged = merged[head + tail]

    st.success(f"Compiled {len(merged)} row(s).")
    st.dataframe(merged.head(20), use_container_width=True)

    st.subheader("4) Download")
    project = best_project_name(calendar_file)
    out_name = f"Compiled Study Data - {project}.xlsx"

    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine="xlsxwriter") as writer:
        merged.to_excel(writer, index=False, sheet_name="Compiled")
    towrite.seek(0)

    st.download_button(
        label=f"⬇️ Download {out_name}",
        data=towrite,
        file_name=out_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
