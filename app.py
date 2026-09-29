"""
app.py
------
Streamlit front-end for the PTU Result Analysis System.
Reads directly from ptu_results.db while preserving all UI, charts, and calculators.
"""

import io
import sqlite3
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # must be set before graphs.py imports pyplot
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from analysis import ResultAnalyzer
from graphs import ResultGraphs

warnings.filterwarnings("ignore", message=".*non-interactive.*")

st.set_page_config(page_title="PTU Result Analysis System", layout="wide")

DB_PATH = Path("ptu_results.db")

# -----------------------------------------------------
# DATA LOADING (from SQLite DB instead of loose CSV)
# -----------------------------------------------------

@st.cache_data(show_spinner="Loading database...")
def load_data_from_db():
    if not DB_PATH.exists():
        return None

    conn = sqlite3.connect(DB_PATH)
    # Reconstruct the analysis DataFrame from the normalized tables
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


def show_fig(plot_fn, *args, **kwargs):
    """Run a ResultGraphs method and display the figure it drew."""
    plot_fn(*args, **kwargs)
    st.pyplot(plt.gcf())
    plt.close("all")


def section_title(text):
    st.markdown(f"## {text}")
    st.markdown(
        "<hr style='margin-top:-8px; margin-bottom:24px;'>",
        unsafe_allow_html=True,
    )


# -----------------------------------------------------
# HEADER
# -----------------------------------------------------

st.markdown("# 🎓 PTU Result Analysis System")
st.markdown(
    "Browse and analyze PTU semester results stored in the relational database. "
    "Pick the semesters you're interested in below to filter every chart and table on this page."
)
st.write("")

df = load_data_from_db()

if df is None or df.empty:
    st.error(
        "Database `ptu_results.db` was not found or is empty. "
        "Run `python migrate_csv.py` first to generate it."
    )
    st.stop()

# Feed reconstructed DataFrame to existing analyzer & graph classes
csv_buffer = io.StringIO(df.to_csv(index=False))
analyzer = ResultAnalyzer(csv_buffer)
graphs = ResultGraphs(io.StringIO(df.to_csv(index=False)))

all_semesters = analyzer.available_semesters()

badge_cols = st.columns(3)
badge_cols[0].caption(f"📄 **{analyzer.total_unique_students()}** unique students")
badge_cols[1].caption(f"🗂️ **{len(all_semesters)}** semesters on record")
badge_cols[2].caption(f"🧾 **{len(analyzer.df)}** total result rows")

# -----------------------------------------------------
# FILTERS
# -----------------------------------------------------

st.markdown("**Which semesters would you like to view?**")
picked_semesters = st.multiselect(
    "Semesters",
    options=all_semesters,
    default=all_semesters,
    label_visibility="collapsed",
)

if not picked_semesters:
    st.warning("Pick at least one semester above to see data.")
    st.stop()

single_semester = picked_semesters[0] if len(picked_semesters) == 1 else None

st.write("")
st.write("")

# -----------------------------------------------------
# SGPA OVER TIME
# -----------------------------------------------------

section_title("SGPA trend across semesters")

trend_rows = []
rate_rows = []
for sem in sorted(picked_semesters):
    stats = analyzer.sgpa_statistics(semester=sem)
    trend_rows.append({
        "Semester": sem,
        "Mean SGPA": stats["Mean"],
        "Highest SGPA": stats["Highest"],
        "Lowest SGPA": stats["Lowest"],
    })
    rate_rows.append({
        "Semester": sem,
        "Pass %": analyzer.pass_percentage(semester=sem),
        "Re-Appear %": analyzer.reappear_percentage(semester=sem),
    })

trend_df = pd.DataFrame(trend_rows).set_index("Semester")
rate_df = pd.DataFrame(rate_rows).set_index("Semester")

chart_col, rate_col = st.columns([3, 2])

with chart_col:
    st.caption("Mean, highest and lowest SGPA per semester")
    st.line_chart(
        trend_df,
        height=380,
        color=["#4C8BF5", "#2ECC71", "#F4574A"],
    )

with rate_col:
    st.caption("Pass vs Re-Appear rate per semester")
    st.bar_chart(
        rate_df,
        height=380,
        color=["#2ECC71", "#F4574A"],
    )

st.write("")
st.write("")

# -----------------------------------------------------
# METRIC CARDS
# -----------------------------------------------------

label = f"Semester {single_semester}" if single_semester else "Selected Semesters"
section_title(f"Results in {label}")

combined = pd.DataFrame()
for sem in picked_semesters:
    scoped = analyzer.df[analyzer.df["Semester"] == sem]
    combined = pd.concat([combined, scoped])

total = len(combined)
passed = len(combined[combined["Result"].str.upper() == "PASS"])
reappear = len(combined[combined["Result"].str.upper() == "RE-APPEAR"])
pass_pct = round((passed / total) * 100, 2) if total else 0
mean_sgpa = round(combined["SGPA"].mean(), 2) if total else 0
highest_sgpa = round(combined["SGPA"].max(), 2) if total else 0

delta_pass_pct = delta_mean_sgpa = None
earlier_semesters = [s for s in all_semesters if s < min(picked_semesters)]
if earlier_semesters:
    prev_sem = max(earlier_semesters)
    prev_stats = analyzer.sgpa_statistics(semester=prev_sem)
    delta_pass_pct = round(pass_pct - analyzer.pass_percentage(semester=prev_sem), 2)
    delta_mean_sgpa = round(mean_sgpa - prev_stats["Mean"], 2)

row1 = st.columns(3)
row1[0].metric("Total Students", total)
row1[1].metric("Passed", passed)
row1[2].metric("Re-Appear", reappear)

row2 = st.columns(3)
row2[0].metric(
    "Pass %", f"{pass_pct}%",
    delta=f"{delta_pass_pct:+g} pts vs Sem {prev_sem}" if delta_pass_pct is not None else None,
)
row2[1].metric(
    "Mean SGPA", mean_sgpa,
    delta=f"{delta_mean_sgpa:+g} vs Sem {prev_sem}" if delta_mean_sgpa is not None else None,
)
row2[2].metric("Highest SGPA", highest_sgpa)

st.write("")

with st.expander("Per-semester breakdown"):
    breakdown_rows = []
    for sem in sorted(picked_semesters):
        s = analyzer.sgpa_statistics(semester=sem)
        breakdown_rows.append({
            "Semester": sem,
            "Total": analyzer.total_students(semester=sem),
            "Passed": analyzer.total_passed(semester=sem),
            "Re-Appear": analyzer.total_reappear(semester=sem),
            "Pass %": analyzer.pass_percentage(semester=sem),
            "Mean SGPA": s["Mean"],
            "Highest SGPA": s["Highest"],
            "Lowest SGPA": s["Lowest"],
        })
    st.dataframe(pd.DataFrame(breakdown_rows), hide_index=True, use_container_width=True)

st.write("")
st.write("")

# -----------------------------------------------------
# DETAILS (search / tables / extra charts)
# -----------------------------------------------------

tab_search, tab_analysis, tab_graphs = st.tabs(
    ["🔍 Student Search", "📋 Tables", "📈 More Charts"]
)

# --- STUDENT SEARCH ---
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
            st.metric(
                "Overall CGPA (credit-weighted)",
                f"{cgpa:.2f}" if cgpa is not None else "N/A",
            )

            rows = []
            for _, rec in history.iterrows():
                sem = int(rec["Semester"])
                rows.append({
                    **rec.to_dict(),
                    "Rank": analyzer.student_rank(roll, semester=sem),
                    "Percentile": analyzer.student_percentile(roll, semester=sem),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

            if analyzer.student_sgpa_trend(roll):
                show_fig(graphs.student_trend_chart, roll)

            # -------------------------------------------------
            # CGPA TARGET CALCULATOR
            # -------------------------------------------------
            st.write("")
            st.markdown("#### 🎯 CGPA Target Calculator")
            st.caption(
                "How high does your average SGPA need to be in the "
                "remaining semesters to hit a target CGPA at graduation?"
            )

            calc_cols = st.columns(2)
            total_program_semesters = calc_cols[0].number_input(
                "Total semesters in the program", min_value=1, max_value=12, value=8
            )
            target_cgpa = calc_cols[1].number_input(
                "Target CGPA", min_value=0.0, max_value=10.0, value=9.0, step=0.05
            )

            completed = history.dropna(subset=["SGPA"])
            completed_semesters = completed["Semester"].nunique()
            remaining_semesters = int(total_program_semesters) - completed_semesters

            if cgpa is None or completed.empty:
                st.info("No valid SGPA on record yet, so a target can't be calculated.")
            elif remaining_semesters <= 0:
                st.info("No semesters remaining based on the total you entered.")
            else:
                current_credits = completed["Credits"].sum()
                avg_credits_per_sem = current_credits / completed_semesters
                remaining_credits = avg_credits_per_sem * remaining_semesters

                current_weighted = cgpa * current_credits
                target_weighted_total = target_cgpa * (current_credits + remaining_credits)
                needed_weighted = target_weighted_total - current_weighted
                required_avg_sgpa = needed_weighted / remaining_credits

                r1, r2, r3 = st.columns(3)
                r1.metric("Current CGPA", f"{cgpa:.2f}")
                r2.metric("Semesters left", remaining_semesters)
                r3.metric(
                    "Required avg SGPA",
                    f"{required_avg_sgpa:.2f}" if required_avg_sgpa <= 10 else "Not possible",
                )

                if required_avg_sgpa > 10:
                    st.warning(
                        f"Even a perfect 10.00 SGPA every remaining semester "
                        f"isn't enough to reach {target_cgpa:.2f} CGPA."
                    )
                elif required_avg_sgpa < 0:
                    st.success(
                        f"Target already secured — even a 0 SGPA the rest of "
                        f"the way keeps CGPA at or above {target_cgpa:.2f}."
                    )
                else:
                    st.success(
                        f"Need an average SGPA of **{required_avg_sgpa:.2f}** "
                        f"across the remaining **{remaining_semesters}** "
                        f"semester(s) to reach **{target_cgpa:.2f}** CGPA."
                    )

                st.caption(
                    "Estimate assumes each remaining semester carries about "
                    f"**{avg_credits_per_sem:.1f}** credits, based on this "
                    "student's own average credits per semester so far."
                )

# --- TABLES ---
with tab_analysis:
    left, right = st.columns(2)

    with left:
        st.subheader("SGPA Statistics")
        st.table(pd.Series(analyzer.sgpa_statistics(semester=single_semester), name="SGPA"))

        st.subheader("Result Counts")
        st.table(pd.Series(analyzer.result_counts(semester=single_semester), name="Students"))

    with right:
        st.subheader("Top 10 Students")
        st.dataframe(analyzer.top_students(10, semester=single_semester),
                     hide_index=True, use_container_width=True)

        st.subheader("Lowest 10 Students")
        st.dataframe(analyzer.lowest_students(10, semester=single_semester),
                     hide_index=True, use_container_width=True)

    st.subheader("Students Currently Re-Appear (latest semester on record)")
    reappear_df = analyzer.currently_reappear_students()
    if reappear_df.empty:
        st.success("No students are currently Re-Appear in their latest semester.")
    else:
        st.dataframe(reappear_df, hide_index=True, use_container_width=True)

    if single_semester is None:
        st.caption(
            "Note: statistics above use a single semester. "
            "Pick just one semester in the filter to scope these tables to it."
        )

# --- MORE CHARTS ---
with tab_graphs:
    charts = {
        "Pass vs Re-Appear Pie Chart": lambda: show_fig(graphs.result_pie_chart, semester=single_semester),
        "Result Distribution Bar Chart": lambda: show_fig(graphs.result_bar_chart, semester=single_semester),
        "SGPA Distribution": lambda: show_fig(graphs.sgpa_distribution, semester=single_semester),
        "SGPA Range Distribution": lambda: show_fig(graphs.sgpa_range_chart, semester=single_semester),
        "Top 10 Students": lambda: show_fig(graphs.top_students_chart, 10, semester=single_semester),
    }

    picked_chart = st.selectbox("Choose a chart", list(charts))
    charts[picked_chart]()