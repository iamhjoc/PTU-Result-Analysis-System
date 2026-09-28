"""
gui.py
------

GUI module for PTU Result Analyzer.

Connects:
- analysis.py
- graphs.py
- results.csv
"""

import tkinter as tk
from tkinter import ttk, messagebox

from analysis import ResultAnalyzer
from graphs import ResultGraphs


class ResultAnalyzerGUI:

    def __init__(self, root):

        self.root = root

        self.root.title("PTU Result Analysis System")
        self.root.geometry("1100x780")
        self.root.minsize(900, 680)

        # -----------------------------------------
        # LOAD MODULES
        # -----------------------------------------

        try:
            self.analyzer = ResultAnalyzer("results.csv")
            self.graphs = ResultGraphs("results.csv")

        except FileNotFoundError:
            messagebox.showerror(
                "File Error",
                "results.csv was not found.\n"
                "Please run extractor.py first."
            )
            self.root.destroy()
            return

        # -----------------------------------------
        # SEMESTER LIST
        # -----------------------------------------

        self.semesters = self.analyzer.available_semesters()

        # "All" plus every semester found in the data
        self.semester_options = ["All"] + [str(s) for s in self.semesters]

        # Currently selected semester scope for dashboard / quick analysis / graphs
        self.selected_semester = tk.StringVar(
            value=self.semester_options[-1] if self.semesters else "All"
        )

        # -----------------------------------------
        # COLORS
        # -----------------------------------------

        self.bg_color = "#F4F6F8"      # Light gray
        self.primary = "#1F4E78"       # Professional blue
        self.secondary = "#D9EAF7"     # Light blue
        self.card_color = "#FFFFFF"    # White
        self.text_color = "#1F2937"    # Dark text

        self.root.configure(bg=self.bg_color)

        self.create_header()
        self.create_semester_selector()
        self.dashboard_container = tk.Frame(self.root, bg=self.bg_color)
        self.dashboard_container.pack(fill="x")
        self.create_dashboard()
        self.create_main_content()

    # =================================================
    # HELPER: current semester filter (None means "All")
    # =================================================

    def _current_semester(self):

        value = self.selected_semester.get()

        if value == "All":
            return None

        return int(value)

    # =================================================
    # HEADER
    # =================================================

    def create_header(self):

        header = tk.Frame(
            self.root,
            bg=self.primary,
            height=80
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="PTU RESULT ANALYSIS SYSTEM",
            font=("Arial", 24, "bold"),
            bg=self.primary,
            fg="white"
        )

        title.pack(
            pady=18
        )

    # =================================================
    # SEMESTER SELECTOR
    # =================================================

    def create_semester_selector(self):

        frame = tk.Frame(
            self.root,
            bg=self.bg_color
        )

        frame.pack(
            fill="x",
            padx=20,
            pady=(12, 0)
        )

        tk.Label(
            frame,
            text="Viewing Semester:",
            font=("Arial", 11, "bold"),
            bg=self.bg_color,
            fg=self.text_color
        ).pack(side="left", padx=(0, 8))

        dropdown = ttk.Combobox(
            frame,
            textvariable=self.selected_semester,
            values=self.semester_options,
            state="readonly",
            width=10
        )

        dropdown.pack(side="left")

        dropdown.bind(
            "<<ComboboxSelected>>",
            self.on_semester_change
        )

    def on_semester_change(self, event=None):

        # Rebuild the dashboard cards for the newly selected semester.
        for widget in self.dashboard_container.winfo_children():
            widget.destroy()

        self.create_dashboard()

    # =================================================
    # DASHBOARD
    # =================================================

    def create_dashboard(self):

        dashboard = tk.Frame(
            self.dashboard_container,
            bg=self.bg_color
        )

        dashboard.pack(
            fill="x",
            padx=20,
            pady=15
        )

        semester = self._current_semester()
        summary = self.analyzer.dashboard_summary(semester=semester)

        cards = [
            ("Total Students", summary["Total Students"]),
            ("Passed", summary["Passed"]),
            ("Re-Appear", summary["Re-Appear"]),
            ("Pass %", f'{summary["Pass Percentage"]}%'),
            ("Mean SGPA", summary["Mean SGPA"]),
            ("Highest SGPA", summary["Highest SGPA"])
        ]

        for i, (title, value) in enumerate(cards):

            card = tk.Frame(
                dashboard,
                bg=self.card_color,
                width=160,
                height=100,
                highlightbackground="#DDDDDD",
                highlightthickness=1
            )

            card.grid(
                row=0,
                column=i,
                padx=7,
                pady=5
            )

            card.grid_propagate(False)

            tk.Label(
                card,
                text=title,
                font=("Arial", 11),
                bg=self.card_color,
                fg="gray"
            ).pack(
                pady=(15, 5)
            )

            tk.Label(
                card,
                text=value,
                font=("Arial", 20, "bold"),
                bg=self.card_color,
                fg=self.primary
            ).pack()

    # =================================================
    # MAIN CONTENT
    # =================================================

    def create_main_content(self):

        container = tk.Frame(
            self.root,
            bg=self.bg_color
        )

        container.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=5
        )

        # LEFT SIDE
        left_frame = tk.Frame(
            container,
            bg=self.card_color,
            width=400
        )

        left_frame.pack(
            side="left",
            fill="both",
            padx=(0, 10),
            expand=False
        )

        # RIGHT SIDE
        right_frame = tk.Frame(
            container,
            bg=self.card_color
        )

        right_frame.pack(
            side="right",
            fill="both",
            expand=True
        )

        self.create_student_search(left_frame)

        self.create_analysis_buttons(left_frame)

        self.create_graph_buttons(right_frame)

    # =================================================
    # STUDENT SEARCH
    # =================================================

    def create_student_search(self, parent):

        frame = tk.Frame(
            parent,
            bg=self.card_color
        )

        frame.pack(
            fill="x",
            padx=25,
            pady=20
        )

        tk.Label(
            frame,
            text="Student Search",
            font=("Arial", 18, "bold"),
            bg=self.card_color,
            fg=self.primary
        ).pack(
            pady=(0, 15)
        )

        tk.Label(
            frame,
            text="Enter Roll Number",
            font=("Arial", 11),
            bg=self.card_color,
            fg=self.text_color
        ).pack(
            anchor="w"
        )

        self.roll_entry = tk.Entry(
            frame,
            font=("Arial", 14),
            width=25
        )

        self.roll_entry.pack(
            pady=7,
            fill="x"
        )

        button_row = tk.Frame(frame, bg=self.card_color)
        button_row.pack(fill="x", pady=5)

        search_button = tk.Button(
            button_row,
            text="SEARCH (Selected Semester)",
            command=self.search_student,
            bg=self.primary,
            fg="white",
            font=("Arial", 10, "bold"),
            relief="flat",
            pady=8,
            cursor="hand2"
        )

        search_button.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 4)
        )

        history_button = tk.Button(
            button_row,
            text="FULL HISTORY",
            command=self.show_student_history,
            bg=self.secondary,
            fg=self.text_color,
            font=("Arial", 10, "bold"),
            relief="flat",
            pady=8,
            cursor="hand2"
        )

        history_button.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(4, 0)
        )

        # RESULT AREA

        self.student_result = tk.Text(
            frame,
            height=15,
            font=("Arial", 12),
            bg="white",
            fg="#222222",
            insertbackground="#222222",
            relief="solid",
            borderwidth=1,
            state="disabled"
        )

        self.student_result.pack(
            fill="both",
            expand=True,
            pady=15
        )

    # =================================================
    # SEARCH STUDENT (within selected semester)
    # =================================================

    def search_student(self):

        roll = self.roll_entry.get().strip()

        if not roll:

            messagebox.showwarning(
                "Input Required",
                "Please enter a Roll Number."
            )

            return

        semester = self._current_semester()

        if semester is None:
            messagebox.showinfo(
                "Select a Semester",
                "Please choose a specific semester from the dropdown "
                "at the top to search a student's result for that "
                "semester, or use FULL HISTORY to see all semesters."
            )
            return

        try:
            student = self.analyzer.get_student(roll, semester=semester)
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        if student is None:

            messagebox.showerror(
                "Not Found",
                f"No record found for Roll Number {roll} in Semester {semester}."
            )

            return

        rank = self.analyzer.student_rank(roll, semester=semester)

        percentile = self.analyzer.student_percentile(roll, semester=semester)

        # SGPA DISPLAY

        sgpa = student["SGPA"]

        if sgpa != sgpa:  # NaN check
            sgpa = "N/A"

        # RANK DISPLAY

        if rank is None:
            rank = "N/A"

        # PERCENTILE DISPLAY

        if percentile is None:
            percentile = "N/A"
        else:
            percentile = f"{percentile}%"

        result_text = f"""
STUDENT DETAILS - SEMESTER {semester}
{'=' * 35}

Roll Number : {student["Roll"]}

Name        : {student["Name"]}

SGPA        : {sgpa}

Credits     : {student["Credits"]}

Result      : {student["Result"]}

Rank        : {rank}

Percentile  : {percentile}
"""

        self._write_result_text(result_text)

    # =================================================
    # FULL HISTORY (all semesters for this student)
    # =================================================

    def show_student_history(self):

        roll = self.roll_entry.get().strip()

        if not roll:

            messagebox.showwarning(
                "Input Required",
                "Please enter a Roll Number."
            )

            return

        history = self.analyzer.student_history(roll)

        if history.empty:

            messagebox.showerror(
                "Not Found",
                f"No records found for Roll Number {roll}."
            )

            return

        cgpa = self.analyzer.student_overall_cgpa(roll)
        cgpa_display = cgpa if cgpa is not None else "N/A"

        text = f"FULL HISTORY - Roll {roll}\n"
        text += "=" * 35 + "\n\n"
        text += history.to_string(index=False)
        text += f"\n\nOverall (credit-weighted) CGPA: {cgpa_display}"

        self._write_result_text(text)

    # =================================================
    # HELPER: write text into the result box
    # =================================================

    def _write_result_text(self, text):

        self.student_result.configure(
            state="normal",
            fg="#222222",
            bg="white"
        )

        self.student_result.delete(
            "1.0",
            tk.END
        )

        self.student_result.insert(
            tk.END,
            text
        )

        self.student_result.configure(
            state="disabled"
        )

    # =================================================
    # ANALYSIS BUTTONS
    # =================================================

    def create_analysis_buttons(self, parent):

        frame = tk.Frame(
            parent,
            bg=self.card_color
        )

        frame.pack(
            fill="x",
            padx=25,
            pady=10
        )

        tk.Label(
            frame,
            text="Quick Analysis (Selected Semester)",
            font=("Arial", 16, "bold"),
            bg=self.card_color,
            fg=self.primary
        ).pack(
            pady=(0, 10)
        )

        buttons = [

            (
                "Show SGPA Statistics",
                self.show_sgpa_statistics
            ),

            (
                "Show Top 10 Students",
                self.show_top_students
            ),

            (
                "Show Lowest 10 Students",
                self.show_lowest_students
            ),

            (
                "Show Result Counts",
                self.show_result_counts
            ),

            (
                "Show Students Currently Re-Appear",
                self.show_currently_reappear
            )
        ]

        for text, command in buttons:

            tk.Button(
                frame,
                text=text,
                command=command,
                bg=self.secondary,
                fg=self.text_color,
                font=("Arial", 10, "bold"),
                relief="flat",
                cursor="hand2",
                pady=7
            ).pack(
                fill="x",
                pady=4
            )

    # =================================================
    # SGPA STATISTICS
    # =================================================

    def show_sgpa_statistics(self):

        semester = self._current_semester()

        stats = self.analyzer.sgpa_statistics(semester=semester)

        text = ""

        for key, value in stats.items():

            text += f"{key}: {value}\n"

        label = f"Semester {semester}" if semester else "All Semesters"

        messagebox.showinfo(
            f"SGPA Statistics - {label}",
            text
        )

    # =================================================
    # TOP STUDENTS
    # =================================================

    def show_top_students(self):

        semester = self._current_semester()

        top = self.analyzer.top_students(10, semester=semester)

        text = top.to_string(
            index=False
        )

        self.show_table_window(
            "Top 10 Students",
            text
        )

    # =================================================
    # LOWEST STUDENTS
    # =================================================

    def show_lowest_students(self):

        semester = self._current_semester()

        students = self.analyzer.lowest_students(10, semester=semester)

        text = students.to_string(
            index=False
        )

        self.show_table_window(
            "Lowest 10 Students",
            text
        )

    # =================================================
    # RESULT COUNTS
    # =================================================

    def show_result_counts(self):

        semester = self._current_semester()

        counts = self.analyzer.result_counts(semester=semester)

        text = ""

        for result, count in counts.items():

            text += f"{result}: {count}\n"

        messagebox.showinfo(
            "Result Distribution",
            text
        )

    # =================================================
    # STUDENTS CURRENTLY RE-APPEAR
    # =================================================

    def show_currently_reappear(self):

        students = self.analyzer.currently_reappear_students()

        if students.empty:
            messagebox.showinfo(
                "Currently Re-Appear",
                "No students are currently Re-Appear in their latest semester."
            )
            return

        text = students.to_string(index=False)

        self.show_table_window(
            "Students Currently Re-Appear (Latest Semester)",
            text
        )

    # =================================================
    # POPUP TABLE WINDOW
    # =================================================

    def show_table_window(
        self,
        title,
        text
    ):

        window = tk.Toplevel(
            self.root
        )

        window.title(title)

        window.geometry(
            "850x400"
        )

        text_box = tk.Text(
            window,
            font=("Courier", 12)
        )

        text_box.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=15
        )

        text_box.insert(
            tk.END,
            text
        )

        text_box.configure(
            state="disabled"
        )

    # =================================================
    # GRAPH BUTTONS
    # =================================================

    def create_graph_buttons(self, parent):

        frame = tk.Frame(
            parent,
            bg=self.card_color
        )

        frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=25
        )

        tk.Label(
            frame,
            text="Visual Analysis (Selected Semester)",
            font=("Arial", 20, "bold"),
            bg=self.card_color,
            fg=self.primary
        ).pack(
            pady=(0, 25)
        )

        graph_buttons = [

            (
                "Pass vs Re-Appear Pie Chart",
                lambda: self.graphs.result_pie_chart(semester=self._current_semester())
            ),

            (
                "Result Distribution Bar Chart",
                lambda: self.graphs.result_bar_chart(semester=self._current_semester())
            ),

            (
                "SGPA Distribution",
                lambda: self.graphs.sgpa_distribution(semester=self._current_semester())
            ),

            (
                "SGPA Range Distribution",
                lambda: self.graphs.sgpa_range_chart(semester=self._current_semester())
            ),

            (
                "Top 10 Students Graph",
                lambda: self.graphs.top_students_chart(10, semester=self._current_semester())
            ),

            (
                "Student SGPA Trend (enter Roll above)",
                self.show_student_trend
            )
        ]

        for text, command in graph_buttons:

            tk.Button(
                frame,
                text=text,
                command=command,
                bg=self.primary,
                fg="white",
                font=("Arial", 13, "bold"),
                relief="flat",
                cursor="hand2",
                pady=12
            ).pack(
                fill="x",
                pady=8
            )

    # =================================================
    # STUDENT TREND GRAPH
    # =================================================

    def show_student_trend(self):

        roll = self.roll_entry.get().strip()

        if not roll:

            messagebox.showwarning(
                "Input Required",
                "Enter a Roll Number in the Student Search box first."
            )

            return

        self.graphs.student_trend_chart(roll)


# =================================================
# RUN APPLICATION
# =================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = ResultAnalyzerGUI(root)

    root.mainloop()
