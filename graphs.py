"""
graphs.py
---------

Graph module for PTU Result Analyzer.

Provides:
1. Pass vs Re-Appear pie chart
2. Result distribution bar chart
3. SGPA distribution histogram
4. SGPA range distribution
5. Top students bar chart
6. Student SGPA trend across semesters (line chart)

Every chart method accepts an optional semester=... argument to scope
the chart to a single semester's data. Leave it as None to combine all
semesters (only meaningful for charts where mixing semesters still makes
sense, e.g. overall result distribution) -- for SGPA-based charts,
mixing semesters can be misleading, so pass semester=... when you have
multiple semesters loaded.
"""

import matplotlib.pyplot as plt
import pandas as pd


class ResultGraphs:

    def __init__(self, csv_path="results.csv"):
        self.df = pd.read_csv(csv_path)

        # Ensure SGPA is numeric
        self.df["SGPA"] = pd.to_numeric(
            self.df["SGPA"],
            errors="coerce"
        )

        # Backwards compatibility with CSVs that predate the Semester column.
        if "Semester" not in self.df.columns:
            self.df["Semester"] = 1

        self.df["Semester"] = pd.to_numeric(
            self.df["Semester"],
            errors="coerce"
        ).astype("Int64")

        self.df["Roll"] = self.df["Roll"].astype(str)

    # -------------------------------------------------
    # INTERNAL HELPER
    # -------------------------------------------------

    def _scoped(self, semester=None):
        if semester is None:
            return self.df
        return self.df[self.df["Semester"] == semester]

    @staticmethod
    def _semester_label(semester):
        return f"Semester {semester}" if semester is not None else "All Semesters"

    # -------------------------------------------------
    # 1. PASS VS RE-APPEAR PIE CHART
    # -------------------------------------------------

    def result_pie_chart(self, semester=None):

        df = self._scoped(semester)
        counts = df["Result"].value_counts()

        plt.figure(figsize=(7, 7))

        plt.pie(
            counts.values,
            labels=counts.index,
            autopct="%1.1f%%",
            startangle=90
        )

        plt.title(f"Result Distribution - {self._semester_label(semester)}")

        plt.tight_layout()
        plt.show()

    # -------------------------------------------------
    # 2. RESULT BAR CHART
    # -------------------------------------------------

    def result_bar_chart(self, semester=None):

        df = self._scoped(semester)
        counts = df["Result"].value_counts()

        plt.figure(figsize=(7, 5))

        plt.bar(
            counts.index,
            counts.values
        )

        plt.xlabel("Result")
        plt.ylabel("Number of Students")
        plt.title(f"Pass vs Re-Appear - {self._semester_label(semester)}")

        # Display numbers above bars
        for i, value in enumerate(counts.values):
            plt.text(
                i,
                value + 3,
                str(value),
                ha="center"
            )

        plt.tight_layout()
        plt.show()

    # -------------------------------------------------
    # 3. SGPA DISTRIBUTION
    # -------------------------------------------------

    def sgpa_distribution(self, semester=None):

        df = self._scoped(semester)
        sgpa = df["SGPA"].dropna()

        plt.figure(figsize=(10, 6))

        plt.hist(
            sgpa,
            bins=10,
            edgecolor="black"
        )

        plt.xlabel("SGPA")
        plt.ylabel("Number of Students")
        plt.title(f"SGPA Distribution - {self._semester_label(semester)}")

        plt.tight_layout()
        plt.show()

    # -------------------------------------------------
    # 4. SGPA RANGE DISTRIBUTION
    # -------------------------------------------------

    def sgpa_range_chart(self, semester=None):

        df = self._scoped(semester)
        sgpa = df["SGPA"].dropna()

        ranges = {
            "5.0 - 5.99": ((sgpa >= 5) & (sgpa < 6)).sum(),
            "6.0 - 6.99": ((sgpa >= 6) & (sgpa < 7)).sum(),
            "7.0 - 7.99": ((sgpa >= 7) & (sgpa < 8)).sum(),
            "8.0 - 8.99": ((sgpa >= 8) & (sgpa < 9)).sum(),
            "9.0 - 10": ((sgpa >= 9) & (sgpa <= 10)).sum()
        }

        plt.figure(figsize=(10, 6))

        plt.bar(
            ranges.keys(),
            ranges.values()
        )

        plt.xlabel("SGPA Range")
        plt.ylabel("Number of Students")
        plt.title(f"Students in Each SGPA Range - {self._semester_label(semester)}")

        plt.xticks(rotation=15)

        # Display count above bars
        for i, value in enumerate(ranges.values()):
            plt.text(
                i,
                value + 1,
                str(value),
                ha="center"
            )

        plt.tight_layout()
        plt.show()

    # -------------------------------------------------
    # 5. TOP STUDENTS CHART
    # -------------------------------------------------

    def top_students_chart(self, n=10, semester=None):

        df = self._scoped(semester)

        top_students = (
            df
            .dropna(subset=["SGPA"])
            .sort_values(
                by="SGPA",
                ascending=False
            )
            .head(n)
        )

        plt.figure(figsize=(12, 6))

        plt.bar(
            top_students["Name"],
            top_students["SGPA"]
        )

        plt.xlabel("Student")
        plt.ylabel("SGPA")
        plt.title(f"Top {n} Students by SGPA - {self._semester_label(semester)}")

        plt.xticks(
            rotation=45,
            ha="right"
        )

        # Display SGPA above bars
        for i, value in enumerate(top_students["SGPA"]):
            plt.text(
                i,
                value + 0.05,
                str(value),
                ha="center"
            )

        plt.ylim(
            min(top_students["SGPA"]) - 0.5,
            10
        )

        plt.tight_layout()
        plt.show()

    # -------------------------------------------------
    # 6. STUDENT SGPA TREND ACROSS SEMESTERS
    # -------------------------------------------------

    def student_trend_chart(self, roll):
        """
        Line chart of one student's SGPA across every semester they have
        a valid SGPA for. Re-Appear semesters (no SGPA) are skipped, but
        printed as a note so the gap in the line isn't mistaken for
        missing data.
        """

        history = (
            self.df[self.df["Roll"] == str(roll)]
            .sort_values("Semester")
        )

        if history.empty:
            print(f"No records found for Roll {roll}")
            return

        valid = history.dropna(subset=["SGPA"])

        if valid.empty:
            print(f"Roll {roll} has no semester with a valid SGPA to plot.")
            return

        plt.figure(figsize=(9, 5))

        plt.plot(
            valid["Semester"],
            valid["SGPA"],
            marker="o",
            linewidth=2
        )

        for x, y in zip(valid["Semester"], valid["SGPA"]):
            plt.text(x, y + 0.1, str(y), ha="center")

        name = history["Name"].iloc[0]

        plt.xlabel("Semester")
        plt.ylabel("SGPA")
        plt.title(f"SGPA Trend - {name} ({roll})")
        plt.xticks(valid["Semester"])
        plt.ylim(0, 10)
        plt.grid(True, linestyle="--", alpha=0.4)

        reappear_semesters = history[
            history["Result"].str.upper() == "RE-APPEAR"
        ]["Semester"].tolist()

        if reappear_semesters:
            plt.figtext(
                0.5, 0.01,
                f"Re-Appear in semester(s): {reappear_semesters}",
                ha="center",
                fontsize=9,
                color="firebrick"
            )

        plt.tight_layout()
        plt.show()


# -------------------------------------------------
# TESTING
# -------------------------------------------------

if __name__ == "__main__":

    graphs = ResultGraphs("results.csv")

    print("Graphs module loaded successfully.")

    # Uncomment any graph to test

    graphs.result_pie_chart()

    # graphs.result_bar_chart(semester=3)

    # graphs.sgpa_distribution(semester=3)

    # graphs.sgpa_range_chart(semester=3)

    # graphs.top_students_chart(semester=3)

    # graphs.student_trend_chart("2416438")
