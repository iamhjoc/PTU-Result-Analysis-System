"""
extractor.py
------------

Extract student result data from one or more PTU Result PDFs.

Handles BOTH table layouts seen in PTU result sheets:

  Format A ("two-row-per-student"):
      Row 1: S.No | Roll | Name/Father(2 lines) | subject codes... | SGPA | Credits | Status | Remarks
      Row 2: (blank leading cells)               | grade letters...
      (Seen in Semester-3 2023 scheme sheets.)

  Format B ("one-row-per-student"):
      Row 1: S.No | Roll | "Name/Father Name" | subject codes... | SGPA | Credits | Status | Remarks
      (Seen in Semester-4 2019 scheme sheets.)

Column positions for SGPA / Credits / Result Status / Roll / Name are
located BY HEADER LABEL on each page rather than hardcoded index, since
the number of subject columns changes across schemes and semesters.

Each row is also tagged with Semester / Scheme / Examination, extracted
from that PDF's own header text, so results from multiple semesters can
be merged into one results.csv without losing per-semester identity.

Output:
    pandas.DataFrame
    results.csv

Author : Himanshu Joshi
"""

import re
from pathlib import Path

import pdfplumber
import pandas as pd


SEMESTER_RE = re.compile(r"Semester[-\s]*(\d+)", re.IGNORECASE)
SCHEME_RE = re.compile(r"SCHEME:\s*(.+?)(?:,?\s*Semester|\s*INSTITUTE)", re.IGNORECASE)
EXAM_RE = re.compile(r"EXAMINATION:\s*([A-Za-z]+-\d{4})", re.IGNORECASE)


class ResultExtractor:

    def __init__(self, pdf_path: str):

        self.pdf_path = Path(pdf_path)

        if not self.pdf_path.exists():
            raise FileNotFoundError(f"{pdf_path} not found")

    # -------------------------------------
    # NORMALIZATION HELPERS
    # -------------------------------------

    @staticmethod
    def _norm(cell):
        """Normalize a table cell: None -> '', collapse whitespace/newlines."""
        if cell is None:
            return ""
        return re.sub(r"\s+", " ", str(cell)).strip()

    @staticmethod
    def _is_blank_row(row):
        return all(ResultExtractor._norm(c) == "" for c in row)

    @staticmethod
    def _find_header_indices(header_row):
        """
        Find the column index for S.No, Roll No, Name, SGPA,
        Credits (Earned) and Result Status by matching header text,
        regardless of exact wording/wrapping.
        """
        idx = {}

        for i, cell in enumerate(header_row):

            text = ResultExtractor._norm(cell).lower()

            if not text:
                continue

            if text.startswith("s.no"):
                idx["sno"] = i
            elif "roll" in text:
                idx["roll"] = i
            elif text.startswith("name"):
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

    # -------------------------------------
    # METADATA (Semester / Scheme / Examination)
    # -------------------------------------

    @staticmethod
    def _extract_sheet_metadata(first_page_text):
        """
        Pull Semester number, Scheme name, and Examination (month-year)
        from the header text of a result PDF's first page. Missing
        fields fall back to '' so a differently worded header doesn't
        crash extraction of everything else.
        """

        meta = {"Semester": "", "Scheme": "", "Examination": ""}

        m = SEMESTER_RE.search(first_page_text)
        if m:
            meta["Semester"] = m.group(1)

        m = SCHEME_RE.search(first_page_text)
        if m:
            meta["Scheme"] = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",")

        m = EXAM_RE.search(first_page_text)
        if m:
            meta["Examination"] = m.group(1)

        return meta

    # -------------------------------------
    # MAIN EXTRACT
    # -------------------------------------

    def extract(self):

        students = []

        with pdfplumber.open(self.pdf_path) as pdf:

            print(f"\nReading {len(pdf.pages)} pages from {self.pdf_path.name}...\n")

            first_page_text = pdf.pages[0].extract_text() or ""
            meta = self._extract_sheet_metadata(first_page_text)

            for page_number, page in enumerate(pdf.pages, start=1):

                tables = page.extract_tables()

                if not tables:
                    continue

                for table in tables:

                    parsed = self._parse_table(table)

                    for record in parsed:
                        record.update(meta)
                        record["SourceFile"] = self.pdf_path.name

                    students.extend(parsed)

                print(f"Page {page_number} done")

        df = pd.DataFrame(students)

        return df

    # -------------------------------------
    # TABLE PARSER (header-driven, handles both layouts)
    # -------------------------------------

    def _parse_table(self, table):

        students = []

        if not table:
            return students

        header = table[0]
        idx = self._find_header_indices(header)

        required = ["roll", "name", "sgpa", "credits", "status"]
        missing = [k for k in required if k not in idx]

        if missing:
            # Not a student-result table (e.g. the grading-scale legend
            # table at the bottom of the page) -- skip silently.
            return students

        row = 1
        n = len(table)

        while row < n:

            current = table[row]

            if self._is_blank_row(current):
                row += 1
                continue

            roll = self._norm(current[idx["roll"]])

            if not roll:
                row += 1
                continue

            try:

                name = self._norm(current[idx["name"]])

                sgpa = self._norm(current[idx["sgpa"]])
                credits = self._norm(current[idx["credits"]])
                status = self._norm(current[idx["status"]])
                remarks = self._norm(current[idx["remarks"]]) if "remarks" in idx else ""

                # Format A: the next physical row belongs to the SAME
                # student (it holds the grade letters) if it has no
                # Roll No / S.No of its own.
                consumed_next = False

                if row + 1 < n:

                    nxt = table[row + 1]
                    nxt_roll = self._norm(nxt[idx["roll"]])
                    nxt_sno = self._norm(nxt[idx.get("sno", idx["roll"])]) if "sno" in idx else ""

                    looks_like_continuation = (
                        not nxt_roll
                        and not nxt_sno
                        and not self._is_blank_row(nxt)
                    )

                    if looks_like_continuation:
                        sgpa = sgpa or self._norm(nxt[idx["sgpa"]])
                        credits = credits or self._norm(nxt[idx["credits"]])
                        status = status or self._norm(nxt[idx["status"]])
                        if "remarks" in idx:
                            remarks = remarks or self._norm(nxt[idx["remarks"]])
                        consumed_next = True

                # SGPA handling (blank for Re-Appear students)
                sgpa = float(sgpa) if sgpa else None

                # Credits
                credits = int(float(credits)) if credits else None

                students.append({
                    "Roll": roll,
                    "Name": name,
                    "SGPA": sgpa,
                    "Credits": credits,
                    "Result": status,
                    "Remarks": remarks,
                })

            except Exception as e:

                print(f"Skipped Row : {current}")
                print(e)

            row += 2 if consumed_next else 1

        return students


# --------------------------------------------------------
# MULTI-FILE HELPER
# --------------------------------------------------------

def extract_many(pdf_paths):
    """
    Extract and merge student records from multiple PTU result PDFs
    (e.g. one per semester) into a single DataFrame.
    """

    frames = []

    for path in pdf_paths:
        extractor = ResultExtractor(path)
        frames.append(extractor.extract())

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    # A student can legitimately appear once per semester, so dedup
    # identity is (Roll, Semester) -- not Roll alone. This only removes
    # true duplicates (e.g. an accidental double table detection on a
    # page), never a student's other-semester record.
    if "Semester" in df.columns:
        df = df.drop_duplicates(subset=["Roll", "Semester"], keep="first")
    else:
        df = df.drop_duplicates(subset=["Roll"], keep="first")

    df = df.reset_index(drop=True)

    return df


# --------------------------------------------------------

def _discover_pdfs(folder="."):
    """
    Find every .pdf file sitting in `folder` (e.g. "1st semester.pdf",
    "2nd semester.pdf", "3rd semester.pdf", "4th semester.pdf", or any
    other PTU result PDFs), sorted by the semester number embedded in
    each PDF's own header text where possible, falling back to filename
    order for any PDF whose semester couldn't be detected.
    """

    pdf_paths = sorted(Path(folder).glob("*.pdf"))

    if not pdf_paths:
        return []

    def _semester_key(path):
        try:
            with pdfplumber.open(path) as pdf:
                text = pdf.pages[0].extract_text() or ""
            meta = ResultExtractor._extract_sheet_metadata(text)
            sem = meta.get("Semester", "")
            return (0, int(sem)) if sem else (1, path.name)
        except Exception:
            return (1, path.name)

    return sorted(pdf_paths, key=_semester_key)


if __name__ == "__main__":

    import sys

    # Usage:
    #   python extractor.py
    #       -> auto-discovers every *.pdf file in the current folder
    #          (e.g. "1st semester.pdf", "2nd semester.pdf", ...),
    #          sorted by semester number, and merges them all.
    #   python extractor.py sem3.pdf sem4.pdf
    #       -> merges only the specific PDFs given.

    if len(sys.argv) > 1:
        pdf_args = sys.argv[1:]
    else:
        pdf_args = [str(p) for p in _discover_pdfs(".")]

        if not pdf_args:
            print("No .pdf files found in this folder, and none given "
                  "on the command line.")
            sys.exit(1)

        print("No PDFs specified -- auto-discovered these files in the current folder:")
        for p in pdf_args:
            print(f"  - {p}")
        print()

    df = extract_many(pdf_args)

    print("\n")
    print(df.head())

    print("\n")
    print(df.info())

    print("\nTotal Students :", len(df))

    df.to_csv("results.csv", index=False)

    print("\nresults.csv created successfully.")