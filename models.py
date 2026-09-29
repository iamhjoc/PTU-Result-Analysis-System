"""
models.py
---------
Relational Database Models for PTU Result Analyzer using SQLAlchemy.
Compatible with SQLite (default) and PostgreSQL.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, 
    DateTime, UniqueConstraint, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class Student(Base):
    __tablename__ = "students"

    roll_no = Column(String(50), primary_key=True)
    name = Column(String(150), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    semester_records = relationship("StudentSemesterRecord", back_populates="student", cascade="all, delete-orphan")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student(roll_no='{self.roll_no}', name='{self.name}')>"


class Semester(Base):
    __tablename__ = "semesters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    semester_num = Column(Integer, nullable=False)
    scheme = Column(String(100), nullable=True)
    examination = Column(String(100), nullable=True)  # e.g., "Nov-2023"

    __table_args__ = (
        UniqueConstraint("semester_num", "scheme", "examination", name="uq_sem_scheme_exam"),
    )

    # Relationships
    records = relationship("StudentSemesterRecord", back_populates="semester_rel")
    grades = relationship("Grade", back_populates="semester_rel")

    def __repr__(self):
        return f"<Semester(sem={self.semester_num}, exam='{self.examination}', scheme='{self.scheme}')>"


class StudentSemesterRecord(Base):
    __tablename__ = "student_semester_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    roll_no = Column(String(50), ForeignKey("students.roll_no", ondelete="CASCADE"), nullable=False)
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    
    sgpa = Column(Float, nullable=True)
    credits_earned = Column(Integer, nullable=True)
    result_status = Column(String(50), nullable=False)  # PASS, RE-APPEAR
    remarks = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("roll_no", "semester_id", name="uq_student_semester"),
    )

    # Relationships
    student = relationship("Student", back_populates="semester_records")
    semester_rel = relationship("Semester", back_populates="records")

    def __repr__(self):
        return f"<SemesterRecord(roll='{self.roll_no}', sem_id={self.semester_id}, SGPA={self.sgpa})>"


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_code = Column(String(50), unique=True, nullable=False)
    subject_name = Column(String(200), nullable=True)

    grades = relationship("Grade", back_populates="subject")

    def __repr__(self):
        return f"<Subject(code='{self.subject_code}')>"


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    roll_no = Column(String(50), ForeignKey("students.roll_no", ondelete="CASCADE"), nullable=False)
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    
    grade_letter = Column(String(10), nullable=True)  # O, A+, A, B+, B, F
    grade_points = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("roll_no", "semester_id", "subject_id", name="uq_student_sem_subject"),
    )

    # Relationships
    student = relationship("Student", back_populates="grades")
    semester_rel = relationship("Semester", back_populates="grades")
    subject = relationship("Subject", back_populates="grades")


def init_db(db_url="sqlite:///ptu_results.db"):
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)