import re
import numpy as np
import pdfplumber
import pandas as pd
import streamlit as st

st.set_page_config(page_title="SA Punters AI", page_icon="🏇", layout="centered", initial_sidebar_state="collapsed")
st.title("🏇 SA Punters Challenge AI")
st.caption("Computaform PDF • Probable Winner • Value Bet • Danger Horse")

def parse_computaform(uploaded_file) -> pd.DataFrame:
    pages = []
    with pdfplumber.open(uploaded_file) as pdf:
        for p in pdf.pages:
            pages.append(p.extract_text() or "")
    full_text = "\n".join(pages)

    course = "SA MEETING"
    cm = re.search(r"TAB\s+(FAIRVIEW|TURFFONTEIN|GREYVILLE|KENILWORTH|VAAL|SCOTTSVILLE|DURBANVILLE)", full_text, re.I)
    if cm:
        course = cm.group(1).upper()

    horse_index = {}
    idx_page = next((p for p in pages if "ALPHABETICAL INDEX TO HORSES" in p.upper()), "")
    for m in re.finditer(r"\bR(\d{1,2})\s+([A-Za-z][A-Za-z\s\'\(\)\-]+?)\s*\.{2,}\s*(\d{1,2})\b", idx_page):
        r_num = int(m.group(1))
        h_key = re.sub(r"[^A-Z]", "", m.group(2).upper())
        s_no = int(m.group(3))
        if h_key:
            horse_index[h_key] = (r_num, s_no, m.group(2).strip().title())

    race_info = {}
    runner_stats = {}

    for txt in pages:
        if "Race Ref:" not in txt or "CFORM RATINGS" not in txt:
            continue

        page_clean = re.sub(r"[^A-Z]", "", txt.upper())
        votes = {}
        for h_key, (r_num, _, _) in horse_index.items():
            if len(h_key) >= 5 and h_key in page_clean:
                votes[r_num] = votes.get(r_num, 0) + 1
        if not votes:
            continue
        r_num = max(votes, key=votes.get)

        dm = re.search(r"\b(\d{3,4})m\b", txt)
        race_info[r_num] = int(dm.group(1)) if dm else 1200

        fb = re.search(r"CFORM RATINGS(.*?)TIPSTER", txt, re.S | re.I)
        if fb:
            for line in fb.group(1).split("\n"):
                if "TOP %" in line or "BEST WEIGHTED" in line:
                    continue
                for bm in re.finditer(r"\b(\d{1,2})\s+[A-Za-z][A-Za-z\s\'\(\)\-]+?\s+([+-]\d+\.\d+)\b", line):
                    runner_stats.setdefault((r_num, int(bm.group(1))), {})["bva"] = float(bm.group(2))
                for im in re.finditer(r"\b(\d{1,2})\s+[A-Za-z][A-Za-z\s\'\(\)\-]+?\s+(\d{1,3})\b", line):
                    no, val = int(im.group(1)), float(im.group(2))
                    ent = runner_stats.setdefault((r_num, no), {})
                    if "cf" not in ent and val <= 75:
                        ent["cf"] = val
                    elif "sp" not in ent:
                        ent["sp"] = val

        top_table = txt.split("CFORM RATINGS")[0]
        for line in top_table.split("\n"):
            m = re.search(r"^\s*(\d{1,2})\s+(?:([\d▲▼]+)\s+)?([A-Z][A-Z\s\'\(\)\-]+?)\s+(\d+)-(\d+)-(\d+)-(\d+)\s+\d+%.*?(\d+[-/]\d+)\s*$", line)
            if not m:
                continue
            no = int(m.group(1))
            l3_digits = [int(d) if d != "0" else 8 for d in re.findall(r"\d", m.group(2) or "")[:3]]
            form_pts = sum((5 - min(d, 5)) * w for d, w in zip(l3_digits, (3, 2, 1)))
            starts, wins = int(m.group(4)), int(m.group(5))
            num, den = map(float, m.group(8).replace("-", "/").split("/"))
            mid = line[m.end(7):m.start(8)]
            cm_conn = re.search(r"\b(\d{1,2})\s+([A-Za-z\s/\.\-]+?)\s+(?:[\d\.]+|--)\s*%\s+\*?([A-Za-z\s/\.\-]+?)\s+(?:[\d\.]+|--)\s*%", mid)
            mr_m = re.search(r"%\s+(?:\d{2,3}\s+)?(\d{2,3})\b", mid)

            ent = runner_stats.setdefault((r_num, no), {})
            ent.update({
                "odds": round((num / den) + 1.0, 2),
                "form_pts": form_pts,
                "win_rate": (wins / starts) if starts > 0 else 0.0,
                "draw": int(cm_conn.group(1)) if cm_conn else no,
                "jockey": cm_conn.group(3).strip() if cm_conn else "TBC",
                "mr": float(mr_m.group(1)) if mr_m else np.nan,
            })

    fields_page = next((p for p in pages if "FIELDS, RATINGS FOR" in p.upper()), "")
    for line in fields_page.split("\n"):
        fm = re.search(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Z][A-Z\s\'\(\)\-]+?)\s+[\d\.]+.*?(\d+/\d+)\s*$", line)
        if fm:
            h_key = re.sub(r"[^A-Z]", "", fm.group(3).upper())
            if h_key in horse_index:
                r_num, s_no, _ = horse_index[h_key]
                num, den = map(float, fm.group(4).split("/"))
                runner_stats.setdefault((r_num, s_no), {}).setdefault("odds", round((num / den) + 1.0, 2))

    rows = []
    for h_key, (r_num, s_no, h_title) in horse_index.items():
        st_data = runner_stats.get((r_num, s_no), {})
        rows.append({
            "course": course, "race_number": r_num, "distance_m": race_info.get(r_num, 1200),
            "saddle_number": s_no, "horse_name": h_title, "draw": st_data.get("draw", s_no),
            "jockey": st_data.get("jockey", "TBC"), "odds": st_data.get("odds", 10.0),
            "cform": st_data.get("cf", np.nan), "speed": st_data.get("sp", np.nan),
            "bva": st_data.get("bva", np.nan), "mr": st_data.get("mr", np.nan),
            "form_pts": st_data.get("form_pts", 0), "win_rate": st_data.get("win_rate", 0.0),
        })
    df = pd.DataFrame(rows)
    return df.sort_values(["race_number", "saddle_number"]) if not df.empty else df

def predict_races(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored, picks = [], []
    for _, grp in df.groupby("race_number", sort=True):
        grp = grp.copy()
        imp = 1.0 / grp["odds"].clip(lower=1.05)
        mkt_p = imp / imp.sum()
        z = np.zeros(len(grp))
        for col, w in [("cform", 0.32), ("speed", 0.25), ("form_pts", 0.15), ("bva", 0.13), ("mr", 0.10), ("win_rate", 0.05)]:
            vals = grp[col].fillna(grp[col].median()).fillna(0).values
            if np.std(vals) > 0:
                z += w * ((vals - np.mean(vals)) / np.std(vals))
        model_p = np.exp(z * 0.55)
        win_p = (0.50 * mkt_p) + (0.50 * (model_p / model_p.sum()))
        grp["win_prob"] = win_p / win_p.sum()
        grp["edge"] = grp["win_prob"] - imp
        grp = grp.sort_values(["win_prob", "odds"], ascending=[False, True]).reset_index(drop=True)
        scored.append(grp)

        rows = [r for _, r in grp.iterrows()]
        pw = next(iter(rows))
        picks.append({**pw, "pick_type": "Probable Winner", "is_top": True})

        val_pool = sorted([r for r in rows[1:] if r["edge"] > 0.02 and r["odds"] >= 2.50], key=lambda x: x["edge"], reverse=True)
        vb = next(iter(val_pool), rows[1] if len(rows) > 1 else pw)
        picks.append({**vb, "pick_type": "Value Bet", "is_top": False})

        used = {pw["horse_name"], vb["horse_name"]}
        dh = next((r for r in rows if r["horse_name"] not in used), rows[-1])
        picks.append({**dh, "pick_type": "Danger Horse", "is_top": False})

    return pd.concat(scored, ignore_index=True), pd.DataFrame(picks)

uploaded_pdf = st.file_uploader("Upload Computaform PDF", type=["pdf"])
if not uploaded_pdf:
    st.info("Tap **Browse files** above to upload your **Computaform PDF**.")
    st.stop()

with st.spinner("Reading Alphabetical Index, Form Ratings & Odds..."):
    runners_df = parse_computaform(uploaded_pdf)
if runners_df.empty:
    st.error("Could not read runners. Please upload an official Computaform PDF.")
    st.stop()

full_df, picks_df = predict_races(runners_df)
course_name = next(iter(full_df["course"]))
tab_card, tab_races = st.tabs(["🏆 Punters Challenge Card", "🔍 Race-by-Race (Top 3)"])

with tab_card:
    st.subheader(f"{course_name} — Punters Card ({full_df['race_number'].nunique()} Races)")
    top_picks = picks_df[picks_df["is_top"]].sort_values("race_number")
    for _, r in top_picks.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns(2)
            c1.markdown(f"**R{int(r['race_number'])}: #{int(r['saddle_number'])} {r['horse_name']}**")
            c1.caption(f"Jockey: {r['jockey']} • Fcst: {r['odds']:.2f} • Edge: {r['edge']:+.1%}")
            c2.metric("Win %", f"{r['win_prob']:.0%}")
    st.download_button("📥 Download Selections (CSV)", picks_df.to_csv(index=False), f"{course_name}_punters.csv", "text/csv", use_container_width=True)

with tab_races:
    sel_r = st.selectbox("Select Race", sorted(full_df["race_number"].unique().tolist()), format_func=lambda x: f"Race {int(x)}")
    r_picks = picks_df[picks_df["race_number"] == sel_r]
    r_field = full_df[full_df["race_number"] == sel_r]
    st.subheader(f"Race {int(sel_r)} — {course_name} ({int(next(iter(r_field['distance_m'])))}m)")
    badges = {"Probable Winner": "🥇", "Value Bet": "💎", "Danger Horse": "⚠️"}
    for _, row in r_picks.iterrows():
        with st.container(border=True):
            st.markdown(f"### {badges[row['pick_type']]} {row['pick_type']}: **#{int(row['saddle_number'])} {row['horse_name']}**\nWin: **{row['win_prob']:.1%}** | Fcst: **{row['odds']:.2f}** | Edge: **{row['edge']:+.1%}** | Jockey: **{row['jockey']}**")
    st.dataframe(r_field[["saddle_number", "horse_name", "jockey", "draw", "cform", "speed", "odds", "win_prob", "edge"]], use_container_width=True, hide_index=True)
