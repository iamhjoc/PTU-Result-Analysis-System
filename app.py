"""
app.py
------

Streamlit front-end for the PTU Result Analysis System.

Replaces gui.py (Tkinter) but reuses, unchanged:
- extractor.py  (PDF -> DataFrame)
- analysis.py   (ResultAnalyzer)
- graphs.py     (ResultGraphs)

Run locally:  streamlit run app.py
"""

import io
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # must be set before graphs.py imports pyplot

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from analysis import ResultAnalyzer
from graphs import ResultGraphs

# graphs.py calls plt.show(), which is a harmless no-op on the Agg backend
warnings.filterwarnings("ignore", message=".*non-interactive.*")

st.set_page_config(page_title="PTU Result Analysis System", layout="wide")


# -----------------------------------------------------
# DATA LOADING
# -----------------------------------------------------

@st.cache_data(show_spinner="Loading results.csv...")
def load_from_csv():
    return pd.read_csv("results.csv")


def get_dataframe():
    if Path("results.csv").exists():
        return load_from_csv()
    return None


def show_fig(plot_fn, *args, **kwargs):
    """Run a ResultGraphs method and display the figure it drew."""
    plot_fn(*args, **kwargs)
    st.pyplot(plt.gcf())
    plt.close("all")


# -----------------------------------------------------
# MAIN
# -----------------------------------------------------

st.title("PTU Result Analysis System")

df = get_dataframe()

if df is None:
    st.error(
        "results.csv was not found. Run extractor.py first to generate it "
        "from your result PDFs, then redeploy."
    )
    st.stop()

csv_text = df.to_csv(index=False)
analyzer = ResultAnalyzer(io.StringIO(csv_text))
graphs = ResultGraphs(io.StringIO(csv_text))

semesters = analyzer.available_semesters()
options = ["All"] + semesters

choice = st.sidebar.selectbox(
    "Viewing semester",
    options,
    index=len(options) - 1,  # latest semester, like the old GUI
)
semester = None if choice == "All" else int(choice)

# Dashboard cards
summary = analyzer.dashboard_summary(semester=semester)
cols = st.columns(6)
cols[0].metric("Total Students", summary["Total Students"])
cols[1].metric("Passed", summary["Passed"])
cols[2].metric("Re-Appear", summary["Re-Appear"])
cols[3].metric("Pass %", f'{summary["Pass Percentage"]}%')
cols[4].metric("Mean SGPA", summary["Mean SGPA"])
cols[5].metric("Highest SGPA", summary["Highest SGPA"])

tab_search, tab_analysis, tab_graphs = st.tabs(
    ["Student Search", "Quick Analysis", "Visual Analysis"]
)

# -----------------------------------------------------
# STUDENT SEARCH
# -----------------------------------------------------

with tab_search:
    roll = st.text_input("Enter Roll Number").strip()

    if roll:
        history = analyzer.student_history(roll)

        if history.empty:
            st.warning(f"No records found for Roll {roll}.")
        else:
            name = df.loc[df["Roll"].astype(str) == roll, "Name"].iloc[0]
            st.subheader(f"{name} ({roll})")

            cgpa = analyzer.student_overall_cgpa(roll)
            st.metric(
                "Overall CGPA (credit-weighted)",
                f"{cgpa:.2f}" if cgpa is not None else "N/A",
            )

            # Per-semester rank and percentile
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

# -----------------------------------------------------
# QUICK ANALYSIS
# -----------------------------------------------------

with tab_analysis:
    left, right = st.columns(2)

    with left:
        st.subheader("SGPA Statistics")
        st.table(pd.Series(analyzer.sgpa_statistics(semester=semester), name="SGPA"))

        st.subheader("Result Counts")
        st.table(pd.Series(analyzer.result_counts(semester=semester), name="Students"))

    with right:
        st.subheader("Top 10 Students")
        st.dataframe(analyzer.top_students(10, semester=semester),
                     hide_index=True, use_container_width=True)

        st.subheader("Lowest 10 Students")
        st.dataframe(analyzer.lowest_students(10, semester=semester),
                     hide_index=True, use_container_width=True)

    st.subheader("Students Currently Re-Appear (latest semester on record)")
    reappear = analyzer.currently_reappear_students()
    if reappear.empty:
        st.success("No students are currently Re-Appear in their latest semester.")
    else:
        st.dataframe(reappear, hide_index=True, use_container_width=True)

# -----------------------------------------------------
# GRAPHS
# -----------------------------------------------------

with tab_graphs:
    charts = {
        "Pass vs Re-Appear Pie Chart": lambda: show_fig(graphs.result_pie_chart, semester=semester),
        "Result Distribution Bar Chart": lambda: show_fig(graphs.result_bar_chart, semester=semester),
        "SGPA Distribution": lambda: show_fig(graphs.sgpa_distribution, semester=semester),
        "SGPA Range Distribution": lambda: show_fig(graphs.sgpa_range_chart, semester=semester),
        "Top 10 Students": lambda: show_fig(graphs.top_students_chart, 10, semester=semester),
    }

    picked = st.selectbox("Choose a chart", list(charts))
    charts[picked]()