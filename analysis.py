"""
analysis.py
-----------

Analysis module for PTU Result Analyzer.

Reads results.csv (produced by extractor.py) and provides functions for
exploring results across ONE OR MORE semesters:

- Mean and median SGPA (overall or per semester)
- Highest and lowest SGPA
- Pass percentage
- Student counts
- Student search (per semester, or full history across semesters)
- Rank / percentile (within a semester)
- Top / lowest students
- Result statistics
- Per-student semester-wise history and SGPA trend
- Credit-weighted overall CGPA across semesters

results.csv is expected to have (at minimum): Roll, Name, SGPA, Credits,
Result. If a Semester column is present, all "per semester" features are
available; if not, the whole file is treated as a single implicit
semester, so this module still works with older single-sheet CSVs.
"""

import pandas as pd


class ResultAnalyzer:

    def __init__(self, csv_path="results.csv"):

        self.df = pd.read_csv(csv_path)

        # Ensure correct data types
        self.df["SGPA"] = pd.to_numeric(
            self.df["SGPA"],
            errors="coerce"
        )

        self.df["Credits"] = pd.to_numeric(
            self.df["Credits"],
            errors="coerce"
        )

        # Backwards compatibility with CSVs that predate the Semester
        # column (single-sheet extraction).
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
        """
        Return the subset of self.df for a given semester, or the whole
        dataframe if semester is None.
        """

        if semester is None:
            return self.df

        subset = self.df[self.df["Semester"] == semester]

        if subset.empty:
            available = sorted(self.df["Semester"].dropna().unique().tolist())
            raise ValueError(
                f"No records found for Semester {semester}. "
                f"Available semesters: {available}"
            )

        return subset

    def available_semesters(self):
        """Return sorted list of semesters present in the data."""
        return sorted(self.df["Semester"].dropna().unique().tolist())

    # -------------------------------------------------
    # BASIC INFORMATION
    # -------------------------------------------------

    def total_students(self, semester=None):
        """Return total number of student records for a semester,
        or across all semesters if semester is None."""
        return len(self._scoped(semester))


    def total_unique_students(self):
        """Return count of distinct students (by Roll) across all semesters."""
        return self.df["Roll"].nunique()


    def total_passed(self, semester=None):
        """Return total number of passed students."""

        df = self._scoped(semester)

        return len(
            df[
                df["Result"].str.upper() == "PASS"
            ]
        )


    def total_reappear(self, semester=None):
        """Return total number of Re-Appear students."""

        df = self._scoped(semester)

        return len(
            df[
                df["Result"].str.upper() == "RE-APPEAR"
            ]
        )


    def pass_percentage(self, semester=None):
        """Calculate pass percentage, optionally scoped to one semester."""

        df = self._scoped(semester)
        total = len(df)

        if total == 0:
            return 0

        passed = len(df[df["Result"].str.upper() == "PASS"])

        return round((passed / total) * 100, 2)


    def reappear_percentage(self, semester=None):
        """Calculate Re-Appear percentage, optionally scoped to one semester."""

        df = self._scoped(semester)
        total = len(df)

        if total == 0:
            return 0

        reappear = len(df[df["Result"].str.upper() == "RE-APPEAR"])

        return round((reappear / total) * 100, 2)

    # -------------------------------------------------
    # SGPA STATISTICS
    # -------------------------------------------------

    def mean_sgpa(self, semester=None):
        """Return mean SGPA."""

        return round(
            self._scoped(semester)["SGPA"].mean(),
            2
        )


    def median_sgpa(self, semester=None):
        """Return median SGPA."""

        return round(
            self._scoped(semester)["SGPA"].median(),
            2
        )


    def highest_sgpa(self, semester=None):
        """Return highest SGPA."""

        return round(
            self._scoped(semester)["SGPA"].max(),
            2
        )


    def lowest_sgpa(self, semester=None):
        """Return lowest valid SGPA."""

        return round(
            self._scoped(semester)["SGPA"].min(),
            2
        )


    def sgpa_statistics(self, semester=None):
        """Return all major SGPA statistics, optionally scoped to one semester."""

        return {
            "Mean": self.mean_sgpa(semester),
            "Median": self.median_sgpa(semester),
            "Highest": self.highest_sgpa(semester),
            "Lowest": self.lowest_sgpa(semester)
        }

    # -------------------------------------------------
    # STUDENT SEARCH
    # -------------------------------------------------

    def get_student(self, roll, semester=None):
        """
        Return a single semester record for a student as a dict.

        If semester is given, returns that semester's record (or None
        if the student has no record for that semester). If semester is
        omitted and the student has exactly one record overall, returns
        that record. If the student has records in multiple semesters
        and none was specified, raises ValueError -- pass semester=...,
        or call student_history(roll) to see everything at once.
        """

        records = self.df[
            self.df["Roll"] == str(roll)
        ]

        if records.empty:
            return None

        if semester is not None:
            record = records[records["Semester"] == semester]
            return record.iloc[0].to_dict() if not record.empty else None

        if len(records) == 1:
            return records.iloc[0].to_dict()

        raise ValueError(
            f"Roll {roll} has records in multiple semesters "
            f"{sorted(records['Semester'].dropna().unique().tolist())}. "
            f"Pass semester=... to get_student(), or call student_history(roll)."
        )


    def student_history(self, roll):
        """
        Return a student's full semester-wise history as a DataFrame,
        sorted by Semester -- the primary way to see how one student has
        performed across every semester on record.
        """

        columns = ["Semester", "Examination", "SGPA", "Credits", "Result"]
        columns = [c for c in columns if c in self.df.columns]

        history = (
            self.df[self.df["Roll"] == str(roll)]
            .sort_values(by="Semester")
        )

        return history[columns].reset_index(drop=True)


    def student_sgpa_trend(self, roll):
        """
        Return a simple {semester: sgpa} dict for a student, useful for
        quickly seeing whether a student is improving, declining, or
        steady across semesters. Semesters with no valid SGPA
        (Re-Appear) are omitted.
        """

        history = self.student_history(roll).dropna(subset=["SGPA"])

        return {
            int(sem): float(sgpa)
            for sem, sgpa in zip(history["Semester"], history["SGPA"])
        }


    def student_overall_cgpa(self, roll):
        """
        Return a credit-weighted average SGPA ("CGPA") across all of a
        student's semesters that have a valid SGPA. Re-Appear semesters
        (no SGPA) are excluded, matching standard CGPA convention.
        Returns None if the student has no semester with a valid SGPA.
        """

        history = self.df[
            self.df["Roll"] == str(roll)
        ].dropna(subset=["SGPA"])

        if history.empty:
            return None

        total_credits = history["Credits"].sum()

        if total_credits == 0:
            return None

        weighted = (history["SGPA"] * history["Credits"]).sum()

        return round(weighted / total_credits, 2)

    # -------------------------------------------------
    # RANK (within a single semester)
    # -------------------------------------------------

    def student_rank(self, roll, semester=None):
        """
        Calculate rank based on SGPA WITHIN the given semester.

        Students with same SGPA receive same rank. If the student has
        records in more than one semester, semester must be specified so
        ranking is against the correct cohort.
        """

        student = self.get_student(roll, semester=semester)

        if student is None:
            return None

        sgpa = student["SGPA"]

        # Re-Appear students have no SGPA
        if pd.isna(sgpa):
            return None

        df = self._scoped(semester if semester is not None else student["Semester"])

        valid_students = df.dropna(
            subset=["SGPA"]
        )

        rank = (
            valid_students["SGPA"]
            .rank(
                method="min",
                ascending=False
            )
        )

        student_index = valid_students[
            (valid_students["Roll"] == str(roll))
            & (valid_students["Semester"] == student["Semester"])
        ].index

        if len(student_index) == 0:
            return None

        return int(rank.loc[student_index[0]])

    # -------------------------------------------------
    # PERCENTILE (within a single semester)
    # -------------------------------------------------

    def student_percentile(self, roll, semester=None):
        """
        Calculate percentile WITHIN the given semester.

        Percentile =
        Number of students with SGPA <= student's SGPA
        ------------------------------------------------ x 100
                   Total valid SGPA students (that semester)
        """

        student = self.get_student(roll, semester=semester)

        if student is None:
            return None

        sgpa = student["SGPA"]

        if pd.isna(sgpa):
            return None

        df = self._scoped(semester if semester is not None else student["Semester"])

        valid_sgpa = df["SGPA"].dropna()

        lesser_or_equal = (
            valid_sgpa <= sgpa
        ).sum()

        total = len(valid_sgpa)

        percentile = (
            lesser_or_equal / total
        ) * 100

        return round(percentile, 2)

    # -------------------------------------------------
    # TOP STUDENTS
    # -------------------------------------------------

    def top_students(self, n=10, semester=None):
        """
        Return top N students according to SGPA, optionally scoped to
        one semester.
        """

        columns = [
            "Roll",
            "Name",
            "Semester",
            "SGPA",
            "Credits",
            "Result"
        ]
        columns = [c for c in columns if c in self.df.columns]

        df = self._scoped(semester)

        top = (
            df
            .dropna(subset=["SGPA"])
            .sort_values(
                by="SGPA",
                ascending=False
            )
            .head(n)
        )

        return top[columns]

    # -------------------------------------------------
    # LOWEST SGPA STUDENTS
    # -------------------------------------------------

    def lowest_students(self, n=10, semester=None):

        columns = [
            "Roll",
            "Name",
            "Semester",
            "SGPA",
            "Credits",
            "Result"
        ]
        columns = [c for c in columns if c in self.df.columns]

        df = self._scoped(semester)

        students = (
            df
            .dropna(subset=["SGPA"])
            .sort_values(
                by="SGPA",
                ascending=True
            )
            .head(n)
        )

        return students[columns]

    # -------------------------------------------------
    # RESULT COUNTS
    # -------------------------------------------------

    def result_counts(self, semester=None):

        return (
            self._scoped(semester)["Result"]
            .value_counts()
            .to_dict()
        )

    # -------------------------------------------------
    # STUDENTS WITH SAME SGPA
    # -------------------------------------------------

    def students_with_sgpa(self, sgpa, semester=None):

        df = self._scoped(semester)

        columns = ["Roll", "Name", "Semester", "SGPA", "Result"]
        columns = [c for c in columns if c in self.df.columns]

        return df[
            df["SGPA"] == sgpa
        ][columns]

    # -------------------------------------------------
    # STUDENTS CURRENTLY RE-APPEAR (most recent semester on record)
    # -------------------------------------------------

    def currently_reappear_students(self):
        """
        Return students whose MOST RECENT semester on record has a
        Re-Appear result -- students who need attention right now,
        regardless of how they did in earlier semesters.
        """

        latest = (
            self.df
            .dropna(subset=["Semester"])
            .sort_values("Semester")
            .groupby("Roll", as_index=False)
            .tail(1)
        )

        columns = ["Roll", "Name", "Semester", "Result", "Credits"]
        columns = [c for c in columns if c in self.df.columns]

        return (
            latest[latest["Result"].str.upper() == "RE-APPEAR"][columns]
            .reset_index(drop=True)
        )

    # -------------------------------------------------
    # COMPLETE DASHBOARD SUMMARY
    # -------------------------------------------------

    def dashboard_summary(self, semester=None):

        return {

            "Semester":
                semester if semester is not None else "All",

            "Total Students":
                self.total_students(semester),

            "Passed":
                self.total_passed(semester),

            "Re-Appear":
                self.total_reappear(semester),

            "Pass Percentage":
                self.pass_percentage(semester),

            "Re-Appear Percentage":
                self.reappear_percentage(semester),

            "Mean SGPA":
                self.mean_sgpa(semester),

            "Median SGPA":
                self.median_sgpa(semester),

            "Highest SGPA":
                self.highest_sgpa(semester),

            "Lowest SGPA":
                self.lowest_sgpa(semester)
        }


# -------------------------------------------------
# TESTING
# -------------------------------------------------

if __name__ == "__main__":

    analyzer = ResultAnalyzer("results.csv")

    print("\n" + "=" * 50)
    print("PTU RESULT ANALYSIS")
    print("=" * 50)

    semesters = analyzer.available_semesters()
    print(f"\nSemesters found in data: {semesters}")
    print(f"Unique students overall: {analyzer.total_unique_students()}")

    for sem in semesters:

        print("\n" + "=" * 50)
        print(f"DASHBOARD SUMMARY - SEMESTER {sem}")
        print("=" * 50)

        summary = analyzer.dashboard_summary(semester=sem)

        for key, value in summary.items():
            print(f"{key}: {value}")

        # Top 10
        print(f"\nTOP 10 STUDENTS - SEMESTER {sem}")

        print(
            analyzer.top_students(10, semester=sem)
            .to_string(index=False)
        )

        # Result distribution
        print(f"\nRESULT DISTRIBUTION - SEMESTER {sem}")

        for result, count in analyzer.result_counts(semester=sem).items():
            print(f"{result}: {count}")

    print("\nAnalysis module working successfully.")
