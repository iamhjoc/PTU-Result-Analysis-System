"""
app.py
------
Streamlit Dashboard connected to ptu_results.db with Subject-Wise Transcripts.
"""

import io
import sqlite3
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from analysis import ResultAnalyzer
from graphs import ResultGraphs

warnings.filterwarnings("ignore", message=".*non-interactive.*")
st.set_page_config(page_title="PTU Result Analysis System", layout="wide")

DB_PATH = Path("ptu_results.db")


@st.cache_data(show_spinner="Loading database...")
def load_data_from_db():
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT 
        s.roll_no AS Roll,
        s.name AS Name,
        sem.semester_num AS Semester,
        sem.scheme AS Scheme,
        sem.examination AS Examination,
        rec.sgpa AS SGPA,
        rec.credits_earned AS Credits,
        rec.result_status AS Result,
        rec.remarks AS Remarks
    FROM student_semester_records rec
    JOIN students s ON rec.roll_no = s.roll_no
    JOIN semesters sem ON rec.semester_id = sem.id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_student_subject_grades(roll_no):
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT 
        sem.semester_num AS Semester,
        sub.subject_code AS [Subject Code],
        g.grade_letter AS [Grade Letter]
    FROM grades g
    JOIN subjects sub ON g.subject_id = sub.id
    JOIN semesters sem ON g.semester_id = sem.id
    WHERE g.roll_no = ?
    ORDER BY sem.semester_num, sub.subject_code
    """
    df_grades = pd.read_sql_query(query, conn, params=[str(roll_no)])
    conn.close()
    return df_grades


def show_fig(plot_fn, *args, **kwargs):
    plot_fn(*args, **kwargs)
    st.pyplot(plt.gcf())
    plt.close("all")


def section_title(text):
    st.markdown(f"## {text}")
    st.markdown("<hr style='margin-top:-8px; margin-bottom:24px;'>", unsafe_allow_html=True)


st.markdown("# 🎓 PTU Result Analysis System")
st.markdown("Browse and analyze PTU semester results stored in the relational database.")
st.write("")

df = load_data_from_db()

if df is None or df.empty:
    st.error("Database `ptu_results.db` not found or empty. Run `python migrate_csv.py` first.")
    st.stop()

analyzer = ResultAnalyzer(io.StringIO(df.to_csv(index=False)))
graphs = ResultGraphs(io.StringIO(df.to_csv(index=False)))

all_semesters = analyzer.available_semesters()

b_cols = st.columns(3)
b_cols[0].caption(f"📄 **{analyzer.total_unique_students()}** unique students")
b_cols[1].caption(f"🗂️ **{len(all_semesters)}** semesters on record")
b_cols[2].caption(f"🧾 **{len(analyzer.df)}** total result records")

st.markdown("**Which semesters would you like to view?**")
picked_semesters = st.multiselect("Semesters", options=all_semesters, default=all_semesters, label_visibility="collapsed")

if not picked_semesters:
    st.warning("Pick at least one semester above.")
    st.stop()

single_semester = picked_semesters[0] if len(picked_semesters) == 1 else None

# SGPA Over Time
section_title("SGPA trend across semesters")
trend_rows, rate_rows = [], []
for sem in sorted(picked_semesters):
    s = analyzer.sgpa_statistics(semester=sem)
    trend_rows.append({"Semester": sem, "Mean SGPA": s["Mean"], "Highest SGPA": s["Highest"], "Lowest SGPA": s["Lowest"]})
    rate_rows.append({"Semester": sem, "Pass %": analyzer.pass_percentage(semester=sem), "Re-Appear %": analyzer.reappear_percentage(semester=sem)})

c_col, r_col = st.columns([3, 2])
with c_col:
    st.caption("Mean, highest and lowest SGPA per semester")
    st.line_chart(pd.DataFrame(trend_rows).set_index("Semester"), height=380, color=["#4C8BF5", "#2ECC71", "#F4574A"])
with r_col:
    st.caption("Pass vs Re-Appear rate per semester")
    st.bar_chart(pd.DataFrame(rate_rows).set_index("Semester"), height=380, color=["#2ECC71", "#F4574A"])

# Metric Cards
label = f"Semester {single_semester}" if single_semester else "Selected Semesters"
section_title(f"Results in {label}")

combined = analyzer.df[analyzer.df["Semester"].isin(picked_semesters)]
total = len(combined)
passed = len(combined[combined["Result"].str.upper() == "PASS"])
reappear = len(combined[combined["Result"].str.upper() == "RE-APPEAR"])
pass_pct = round((passed / total) * 100, 2) if total else 0
mean_sgpa = round(combined["SGPA"].mean(), 2) if total else 0
highest_sgpa = round(combined["SGPA"].max(), 2) if total else 0

row1 = st.columns(3)
row1[0].metric("Total Students", total)
row1[1].metric("Passed", passed)
row1[2].metric("Re-Appear", reappear)

row2 = st.columns(3)
row2[0].metric("Pass %", f"{pass_pct}%")
row2[1].metric("Mean SGPA", mean_sgpa)
row2[2].metric("Highest SGPA", highest_sgpa)

st.write("")

tab_search, tab_analysis, tab_graphs = st.tabs(["🔍 Student Search", "📋 Tables", "📈 More Charts"])

with tab_search:
    roll = st.text_input("Enter Roll Number").strip()
    if roll:
        history = analyzer.student_history(roll)
        if history.empty:
            st.warning(f"No records found for Roll {roll}.")
        else:
            name_match = df.loc[df["Roll"].astype(str) == roll, "Name"]
            name = name_match.iloc[0] if not name_match.empty else "Unknown"
            st.subheader(f"{name} ({roll})")

            cgpa = analyzer.student_overall_cgpa(roll)
            st.metric("Overall CGPA (credit-weighted)", f"{cgpa:.2f}" if cgpa is not None else "N/A")

            st.write("##### Semester Summary")
            rows = []
            for _, rec in history.iterrows():
                sem = int(rec["Semester"])
                rows.append({
                    **rec.to_dict(),
                    "Rank": analyzer.student_rank(roll, semester=sem),
                    "Percentile": analyzer.student_percentile(roll, semester=sem),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True)

            # Display Subject-Wise Grades
            grades_history = get_student_subject_grades(roll)
            if not grades_history.empty:
                st.write("##### 📚 Subject-wise Grades")
                st.dataframe(grades_history, hide_index=True)
            else:
                st.info("No subject-wise grade data found for this student.")

            if analyzer.student_sgpa_trend(roll):
                show_fig(graphs.student_trend_chart, roll)

            # CGPA Target Calculator
            st.write("")
            st.markdown("#### 🎯 CGPA Target Calculator")
            calc_cols = st.columns(2)
            total_program_semesters = calc_cols[0].number_input("Total semesters in program", min_value=1, max_value=12, value=8)
            target_cgpa = calc_cols[1].number_input("Target CGPA", min_value=0.0, max_value=10.0, value=9.0, step=0.05)

            completed = history.dropna(subset=["SGPA"])
            completed_semesters = completed["Semester"].nunique()
            remaining_semesters = int(total_program_semesters) - completed_semesters

            if cgpa is not None and not completed.empty and remaining_semesters > 0:
                current_credits = completed["Credits"].sum()
                avg_credits = current_credits / completed_semesters
                rem_credits = avg_credits * remaining_semesters
                needed_sgpa = ((target_cgpa * (current_credits + rem_credits)) - (cgpa * current_credits)) / rem_credits

                r1, r2, r3 = st.columns(3)
                r1.metric("Current CGPA", f"{cgpa:.2f}")
                r2.metric("Semesters left", remaining_semesters)
                r3.metric("Required avg SGPA", f"{needed_sgpa:.2f}" if needed_sgpa <= 10 else "Not possible")

with tab_analysis:
    l_col, r_col = st.columns(2)
    with l_col:
        st.subheader("SGPA Statistics")
        st.table(pd.Series(analyzer.sgpa_statistics(semester=single_semester), name="SGPA"))
        st.subheader("Result Counts")
        st.table(pd.Series(analyzer.result_counts(semester=single_semester), name="Students"))
    with r_col:
        st.subheader("Top 10 Students")
        st.dataframe(analyzer.top_students(10, semester=single_semester), hide_index=True)
        st.subheader("Lowest 10 Students")
        st.dataframe(analyzer.lowest_students(10, semester=single_semester), hide_index=True)

with tab_graphs:
    charts = {
        "Pass vs Re-Appear Pie Chart": lambda: show_fig(graphs.result_pie_chart, semester=single_semester),
        "Result Distribution Bar Chart": lambda: show_fig(graphs.result_bar_chart, semester=single_semester),
        "SGPA Distribution": lambda: show_fig(graphs.sgpa_distribution, semester=single_semester),
        "SGPA Range Distribution": lambda: show_fig(graphs.sgpa_range_chart, semester=single_semester),
        "Top 10 Students": lambda: show_fig(graphs.top_students_chart, 10, semester=single_semester),
    }
    picked = st.selectbox("Choose a chart", list(charts))
    charts[picked]()