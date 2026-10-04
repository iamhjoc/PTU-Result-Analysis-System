"""
migrate_csv.py
--------------
Safely merges results.csv and subject_grades.csv into ptu_results.db.
Performs upserts to update Re-Appear records without constraint collisions.
"""

from pathlib import Path
import pandas as pd
from models import init_db, Student, Semester, StudentSemesterRecord, Subject, Grade

def migrate():
    results_path = Path("results.csv")
    grades_path = Path("subject_grades.csv")

    if not results_path.exists():
        print("❌ Error: results.csv not found. Run extractor.py first.")
        return

    Session = init_db("sqlite:///ptu_results.db")
    session = Session()

    print("⏳ Migrating Student Summaries from results.csv...")
    df_results = pd.read_csv(results_path)

    for _, row in df_results.iterrows():
        roll = str(row["Roll"]).strip()
        name = str(row.get("Name", "Unknown")).strip()
        father_name = str(row.get("Father_Name", "")).strip() if pd.notna(row.get("Father_Name")) else ""
        sem_num = int(row["Semester"]) if pd.notna(row.get("Semester")) else 1
        exam = str(row.get("Examination", "Default")).strip()
        scheme = str(row.get("Scheme", "Default")).strip()

        # 1. Upsert Student Master
        student = session.query(Student).filter_by(roll_no=roll).first()
        if not student:
            student = Student(roll_no=roll, name=name)
            session.add(student)
            session.flush()
        else:
            if name and student.name == "Unknown":
                student.name = name

        # 2. Get or Create Semester
        sem = session.query(Semester).filter_by(semester_num=sem_num).first()
        if not sem:
            sem = Semester(semester_num=sem_num, scheme=scheme, examination=exam)
            session.add(sem)
            session.flush()

        # 3. Upsert Student Semester Record
        record = session.query(StudentSemesterRecord).filter_by(
            roll_no=roll, semester_id=sem.id
        ).first()

        sgpa = float(row["SGPA"]) if pd.notna(row.get("SGPA")) else None
        try:
            credits_val = int(float(row["Credits"])) if pd.notna(row.get("Credits")) else None
        except ValueError:
            credits_val = None

        res_status = str(row.get("Result", "PASS")).strip()
        remarks_val = str(row.get("Remarks", "")) if pd.notna(row.get("Remarks")) else ""

        if not record:
            record = StudentSemesterRecord(
                roll_no=roll,
                semester_id=sem.id,
                sgpa=sgpa,
                credits_earned=credits_val,
                result_status=res_status,
                remarks=remarks_val
            )
            session.add(record)
        else:
            # Update record if student cleared re-appear or obtained an SGPA
            if sgpa is not None:
                record.sgpa = sgpa
            if credits_val is not None:
                record.credits_earned = credits_val
            record.result_status = res_status
            if remarks_val:
                record.remarks = remarks_val

    session.commit()
    print("✅ Student summaries successfully migrated.")

    # 4. Upsert Subject Grades
    if grades_path.exists():
        print("⏳ Migrating Subject Grades from subject_grades.csv...")
        df_grades = pd.read_csv(grades_path)

        for _, row in df_grades.iterrows():
            roll = str(row["Roll"]).strip()
            sem_num = int(row["Semester"]) if pd.notna(row.get("Semester")) else 1
            sub_code = str(row["Subject_Code"]).strip()
            grade_letter = str(row["Grade"]).strip()

            subject = session.query(Subject).filter_by(subject_code=sub_code).first()
            if not subject:
                subject = Subject(subject_code=sub_code, subject_name=sub_code)
                session.add(subject)
                session.flush()

            sem = session.query(Semester).filter_by(semester_num=sem_num).first()
            if not sem:
                continue

            existing_grade = session.query(Grade).filter_by(
                roll_no=roll, semester_id=sem.id, subject_id=subject.id
            ).first()

            if not existing_grade:
                session.add(Grade(
                    roll_no=roll,
                    semester_id=sem.id,
                    subject_id=subject.id,
                    grade_letter=grade_letter
                ))
            else:
                # Update with the new grade (e.g., cleared backlog)
                existing_grade.grade_letter = grade_letter

        session.commit()
        print("✅ Subject grades successfully migrated.")

    session.close()
    print("🚀 Migration finished: ptu_results.db is up to date.")

if __name__ == "__main__":
    migrate()