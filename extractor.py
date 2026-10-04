"""
extractor.py
------------
Extract student summaries and individual subject letter grades from PTU Result PDFs.
Handles:
- Both 1-row-per-student and 2-row-per-student table formats.
- Regular and Re-Appear / Re-evaluation result gazettes.
"""

import re
import sys
from pathlib import Path
import pdfplumber
import pandas as pd

SEMESTER_RE = re.compile(r"Semester[-\s]*(\d+)", re.IGNORECASE)
SCHEME_RE = re.compile(r"SCHEME:\s*(.+?)(?:,?\s*Semester|\s*INSTITUTE)", re.IGNORECASE)
EXAM_RE = re.compile(r"EXAMINATION:\s*([A-Za-z]+-\d{4})", re.IGNORECASE)
RESULT_TYPE_RE = re.compile(r"RESULT TYPE:\s*([A-Za-z\-]+)", re.IGNORECASE)


class ResultExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"{pdf_path} not found")

    @staticmethod
    def _norm(cell):
        if cell is None:
            return ""
        return re.sub(r"\s+", " ", str(cell)).strip()

    @staticmethod
    def _clean_subject_code(raw_text):
        s = str(raw_text).strip()
        # Connect split hyphens like 'BTCS-401\n-18' or 'BTPH102- 23'
        s = re.sub(r"-\s+", "-", s)
        s = re.sub(r"\s+-", "-", s)
        # Collapse internal multiple spaces and newlines
        s = re.sub(r"\s+", " ", s).strip()
        # Strip trailing credit digit (e.g. 'BTPH101-23 4' -> 'BTPH101-23')
        s = re.sub(r"\s+\d+$", "", s).strip()
        return s
    
    @staticmethod
    def _is_blank_row(row):
        return all(ResultExtractor._norm(c) == "" for c in row)

    @staticmethod
    def _extract_sheet_metadata(first_page_text):
        meta = {
            "Semester": "",
            "Scheme": "",
            "Examination": "",
            "ResultType": "Regular",
        }
        m = SEMESTER_RE.search(first_page_text)
        if m:
            meta["Semester"] = m.group(1)
        m = SCHEME_RE.search(first_page_text)
        if m:
            meta["Scheme"] = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",")
        m = EXAM_RE.search(first_page_text)
        if m:
            meta["Examination"] = m.group(1)
        m_type = RESULT_TYPE_RE.search(first_page_text)
        if m_type:
            meta["ResultType"] = m_type.group(1).strip()
        return meta

    @staticmethod
    def _find_column_bounds(header_row):
        idx = {}
        for i, cell in enumerate(header_row):
            text = ResultExtractor._norm(cell).lower()
            if not text:
                continue
            if text.startswith("s.no"):
                idx["sno"] = i
            elif "roll" in text:
                idx["roll"] = i
            elif "name" in text:
                idx["name"] = i
            elif text == "sgpa":
                idx["sgpa"] = i
            elif "credits" in text:
                idx["credits"] = i
            elif "result" in text and "status" in text:
                idx["status"] = i
            elif text == "remarks":
                idx["remarks"] = i
        return idx

    def extract(self):
        student_records = []
        subject_grades = []

        with pdfplumber.open(self.pdf_path) as pdf:
            first_page_text = pdf.pages[0].extract_text() or ""
            meta = self._extract_sheet_metadata(first_page_text)

            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header = table[0]
                    bounds = self._find_column_bounds(header)

                    required = ["roll", "name", "sgpa", "credits", "status"]
                    if any(k not in bounds for k in required):
                        continue

                    name_idx = bounds["name"]
                    sgpa_idx = bounds["sgpa"]

                    # Format B check: subject codes in header row
                    is_format_b = False
                    header_subjects = {}
                    for col_idx in range(name_idx + 1, sgpa_idx):
                        cell_val = self._norm(header[col_idx])
                        if cell_val and "detail" not in cell_val.lower():
                            header_subjects[col_idx] = self._clean_subject_code(cell_val)
                            is_format_b = True

                    row_idx = 1
                    total_rows = len(table)

                    while row_idx < total_rows:
                        curr = table[row_idx]
                        if self._is_blank_row(curr):
                            row_idx += 1
                            continue

                        roll = self._norm(curr[bounds["roll"]])
                        if not roll or not roll.isdigit():
                            row_idx += 1
                            continue

                        # New code: splits first, keeping only the student's actual name
                        raw_name_cell = str(curr[bounds["name"]]) if curr[bounds["name"]] is not None else ""
                        name_lines = [re.sub(r"\s+", " ", line).strip() for line in raw_name_cell.split("\n") if line.strip()]

                        student_name = name_lines[0] if name_lines else ""
                        father_name = name_lines[1] if len(name_lines) > 1 else ""
                        sgpa_raw = self._norm(curr[bounds["sgpa"]])
                        credits_raw = self._norm(curr[bounds["credits"]])
                        status = self._norm(curr[bounds["status"]])
                        remarks = self._norm(curr[bounds["remarks"]]) if "remarks" in bounds else ""

                        consumed_next = False
                        student_grades_list = []

                        if not is_format_b:
                            # Format A: 2 physical rows per student
                            if row_idx + 1 < total_rows:
                                nxt = table[row_idx + 1]
                                if not self._norm(nxt[bounds["roll"]]):
                                    sgpa_raw = sgpa_raw or self._norm(nxt[bounds["sgpa"]])
                                    credits_raw = credits_raw or self._norm(nxt[bounds["credits"]])
                                    status = status or self._norm(nxt[bounds["status"]])

                                    for c in range(name_idx + 1, sgpa_idx):
                                        sub_code = self._clean_subject_code(self._norm(curr[c]))
                                        grade_letter = self._norm(nxt[c])
                                        if sub_code and grade_letter:
                                            student_grades_list.append((sub_code, grade_letter))

                                    consumed_next = True
                        else:
                            # Format B: 1 physical row per student
                            for c, sub_code in header_subjects.items():
                                grade_letter = self._norm(curr[c])
                                if grade_letter:
                                    student_grades_list.append((sub_code, grade_letter))

                        sgpa = float(sgpa_raw) if sgpa_raw else None
                        try:
                            credits_val = int(float(credits_raw)) if credits_raw else None
                        except ValueError:
                            credits_val = None

                        student_records.append({
                            "Roll": roll,
                            "Name": student_name,
                            "Father_Name": father_name,
                            "Semester": meta.get("Semester", ""),
                            "Scheme": meta.get("Scheme", ""),
                            "Examination": meta.get("Examination", ""),
                            "ResultType": meta.get("ResultType", "Regular"),
                            "SGPA": sgpa,
                            "Credits": credits_val,
                            "Result": status,
                            "Remarks": remarks,
                            "SourceFile": self.pdf_path.name
                        })

                        for sub_code, grade in student_grades_list:
                            subject_grades.append({
                                "Roll": roll,
                                "Semester": meta.get("Semester", ""),
                                "Subject_Code": sub_code,
                                "Grade": grade,
                                "ResultType": meta.get("ResultType", "Regular")
                            })

                        row_idx += 2 if consumed_next else 1

        return pd.DataFrame(student_records), pd.DataFrame(subject_grades)


def extract_all(pdf_paths):
    all_records, all_grades = [], []

    # Sort regular PDFs first, Re-Appear PDFs second so reappear data takes precedence
    def _sort_key(p):
        name = Path(p).name.lower()
        is_reappear = 1 if ("re" in name or "reappear" in name) else 0
        return (is_reappear, name)

    sorted_paths = sorted(pdf_paths, key=_sort_key)

    for path in sorted_paths:
        print(f"Reading: {Path(path).name}...")
        extractor = ResultExtractor(path)
        records, grades = extractor.extract()
        all_records.append(records)
        all_grades.append(grades)

    if not all_records:
        print("No records extracted.")
        return

    df_records = pd.concat(all_records, ignore_index=True)
    df_grades = pd.concat(all_grades, ignore_index=True)

    # Sort so Re-Appear rows come after Regular rows, then keep='last'
    df_records["_sort"] = df_records["ResultType"].apply(lambda x: 1 if "re" in str(x).lower() else 0)
    df_records = df_records.sort_values(by=["Roll", "Semester", "_sort"]).drop_duplicates(
        subset=["Roll", "Semester"], keep="last"
    ).drop(columns=["_sort"])

    df_grades["_sort"] = df_grades["ResultType"].apply(lambda x: 1 if "re" in str(x).lower() else 0)
    df_grades = df_grades.sort_values(by=["Roll", "Semester", "Subject_Code", "_sort"]).drop_duplicates(
        subset=["Roll", "Semester", "Subject_Code"], keep="last"
    ).drop(columns=["_sort"])

    df_records.to_csv("results.csv", index=False)
    df_grades.to_csv("subject_grades.csv", index=False)
    print(f"Extraction Done: {len(df_records)} student rows, {len(df_grades)} grade rows saved.")


if __name__ == "__main__":
    pdfs = sys.argv[1:] if len(sys.argv) > 1 else sorted(Path(".").glob("*.pdf"))
    if pdfs:
        extract_all(pdfs)
    else:
        print("No PDF files found in current directory.")