# Calendar + Screener Compiler (Streamlit)

A zero-setup web app (Streamlit) that merges your **Calendar** and **Screener** files into a clean Excel for your study.

## Features
- Auto-detects **calendar** (or **calender**) and **screener** by filename
- Robust header mapping
- Joins on **EMAIL** (case-insensitive)
- Removes linking fields from final output
- Exports `Compiled Study Data - <project>.xlsx`

## Local Run
```bash
pip install -r requirements.txt
streamlit run app.py
