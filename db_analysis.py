"""
db_analysis.py
--------------
SQLAlchemy-backed replacement for analysis.py.
"""

from sqlalchemy import func
import pandas as pd
from models import init_db, Student, Semester, StudentSemesterRecord, Subject, Grade

class DBResultAnalyzer:

    def __init__(self, db_url="sqlite:///ptu_results.db"):
        self.Session = init_db(db_url)

    def available_semesters(self):
        session = self.Session()
        sems = session.query(Semester.semester_num).distinct().order_by(Semester.semester_num).all()
        session.close()
        return [s[0] for s in sems]

    def dashboard_summary(self, semester_num=None):
        session = self.Session()
        query = session.query(StudentSemesterRecord).join(Semester)
        
        if semester_num is not None:
            query = query.filter(Semester.semester_num == semester_num)

        total_students = query.count()
        passed = query.filter(func.upper(StudentSemesterRecord.result_status) == "PASS").count()
        reappear = query.filter(func.upper(StudentSemesterRecord.result_status) == "RE-APPEAR").count()

        sgpa_query = query.filter(StudentSemesterRecord.sgpa.isnot(None))
        stats = sgpa_query.with_entities(
            func.avg(StudentSemesterRecord.sgpa),
            func.max(StudentSemesterRecord.sgpa),
            func.min(StudentSemesterRecord.sgpa)
        ).first()

        mean_sgpa = round(stats[0], 2) if stats and stats[0] else 0.0
        highest_sgpa = round(stats[1], 2) if stats and stats[1] else 0.0
        lowest_sgpa = round(stats[2], 2) if stats and stats[2] else 0.0

        session.close()
        return {
            "Semester": semester_num if semester_num else "All",
            "Total Students": total_students,
            "Passed": passed,
            "Re-Appear": reappear,
            "Pass Percentage": round((passed / total_students * 100), 2) if total_students else 0.0,
            "Mean SGPA": mean_sgpa,
            "Highest SGPA": highest_sgpa,
            "Lowest SGPA": lowest_sgpa
        }

    def student_history(self, roll_no):
        session = self.Session()
        records = (
            session.query(
                Semester.semester_num.label("Semester"),
                Semester.examination.label("Examination"),
                StudentSemesterRecord.sgpa.label("SGPA"),
                StudentSemesterRecord.credits_earned.label("Credits"),
                StudentSemesterRecord.result_status.label("Result")
            )
            .join(Semester, StudentSemesterRecord.semester_id == Semester.id)
            .filter(StudentSemesterRecord.roll_no == str(roll_no))
            .order_by(Semester.semester_num)
            .all()
        )
        session.close()
        return pd.DataFrame([r._asdict() for r in records])

    def top_students(self, n=10, semester_num=None):
        session = self.Session()
        query = (
            session.query(
                Student.roll_no.label("Roll"),
                Student.name.label("Name"),
                Semester.semester_num.label("Semester"),
                StudentSemesterRecord.sgpa.label("SGPA"),
                StudentSemesterRecord.credits_earned.label("Credits"),
                StudentSemesterRecord.result_status.label("Result")
            )
            .join(Student, StudentSemesterRecord.roll_no == Student.roll_no)
            .join(Semester, StudentSemesterRecord.semester_id == Semester.id)
            .filter(StudentSemesterRecord.sgpa.isnot(None))
        )

        if semester_num is not None:
            query = query.filter(Semester.semester_num == semester_num)

        results = query.order_by(StudentSemesterRecord.sgpa.desc()).limit(n).all()
        session.close()
        return pd.DataFrame([r._asdict() for r in results])