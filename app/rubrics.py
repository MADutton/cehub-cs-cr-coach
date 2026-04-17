from __future__ import annotations

CR_SECTIONS = [
    {"key": "title",               "label": "Title",                  "max_pts": 20},
    {"key": "introduction_of_topic","label": "Introduction of Topic",  "max_pts": 30},
    {"key": "literature_review",   "label": "Literature Review",       "max_pts": 80},
    {"key": "case_report",         "label": "Case Report",             "max_pts": 120},
    {"key": "discussion_critique", "label": "Discussion & Critique",   "max_pts": 100},
    {"key": "endnotes",            "label": "Endnotes",                "max_pts": 20},
    {"key": "references",          "label": "References",              "max_pts": 30},
    {"key": "labs_tables",         "label": "Labs / Tables",           "max_pts": 20},
]
CR_MAX = 420
CR_PASS = 294

CS_SECTIONS = [
    {"key": "title",                        "label": "Title",                           "max_pts": 10},
    {"key": "introduction",                 "label": "Introduction",                    "max_pts": 20},
    {"key": "treatment_management_prognosis","label": "Treatment / Management / Prognosis","max_pts": 80},
    {"key": "case_history_presentation",    "label": "Case History & Presentation",     "max_pts": 80},
    {"key": "case_management_outcome",      "label": "Case Management & Outcome",       "max_pts": 80},
    {"key": "discussion_critique",          "label": "Discussion & Critique",           "max_pts": 100},
    {"key": "references_endnotes",          "label": "References & Endnotes",           "max_pts": 10},
    {"key": "lab_data_imaging",             "label": "Lab Data & Imaging",              "max_pts": 20},
]
CS_MAX = 400
CS_PASS = 280

CR_RUBRIC = """CASE REPORT RUBRIC — score each section 0-4 pts.

TITLE (max 20 pts):
4 — Title accurately describes the contents of the case report
2 — Title somewhat describes the contents of the case report
0 — Title does not accurately describe the contents of the case report

INTRODUCTION OF TOPIC (max 30 pts):
4 — Complete overview of the general concept (~1 paragraph)
3 — Mostly complete overview (~1 paragraph)
2 — Somewhat complete overview (may be >1 paragraph)
1 — Incomplete overview
0 — Missing or does not provide an overview

LITERATURE REVIEW (max 80 pts):
4 — Current, high-quality literature. ≤3 top clinical problems stated. Complete, concise description of pathophysiology, typical history/presentation, differential diagnoses, diagnostic approach. Complete synopsis of treatment/management and current recommended therapies. Expected outcome and prognosis discussed.
3 — Mostly complete. 1-2 significant omissions.
2 — Somewhat complete. >2 significant omissions. Literature may be older or moderate quality.
1 — Not current/high quality. Many significant omissions.
0 — Not current, low quality, and incomplete. Missing core elements. Prognosis not discussed.

CASE REPORT (max 120 pts):
4 — Complete description of patient/population, chief complaint, and relevant history/clinical findings. All relevant procedures, medications, complications, co-morbidities, and justification for deviations discussed. Full outcome including patient/case outcome, results of procedures/medical management, and full follow-up.
3 — Mostly complete. 1-2 significant omissions.
2 — Somewhat complete. >2 significant omissions.
1 — Minimal description. Many significant omissions.
0 — Description of patient, chief complaint, history and clinical findings are incomplete or missing. Relevant procedures, medications, complications, co-morbidities are incomplete or missing. Outcome, results, and follow-up are incomplete or missing.

DISCUSSION AND CRITIQUE (max 100 pts):
4 — Complete constructive evaluation of case deficiencies, mistakes, and/or complications. Identifies potential changes for future cases. Demonstrates ability to learn from an imperfect case. No new material added.
3 — Mostly complete. 1-2 significant omissions. Minimal new material may have been added.
2 — Somewhat complete. >2 significant omissions. New material may have been added.
1 — Minimal constructive evaluation. Many significant omissions. Significant new material may have been added.
0 — Does not critically evaluate deficiencies. Unable to identify changes for future cases. Does not demonstrate learning. Significant new material added.

ENDNOTES (max 20 pts):
4 — Endnotes present and properly cited for all appropriate items
3 — Endnotes mostly present and properly cited
2 — Endnotes absent and/or improperly cited
0 — No endnotes

REFERENCES (max 30 pts):
4 — Current, applicable, and comprehensive for all problems identified and discussed
3 — Most relevant and current applicable references cited
2 — References listed but more current/specific references are available
1 — Very few relevant references
0 — References inappropriate or incomplete

LABS / TABLES (max 20 pts):
4 — Lab results relevant to the case and clearly displayed and described
2 — Lab results present but not entirely relevant or could be more clearly displayed/described
0 — Lab results missing, not relevant, or illegible without description

OVERALL IMPRESSIONS (Pass/Fail — a "No" on either fails the entire paper):
A — Case demonstrates management commensurate with ABVP diplomate level of practice: clinical acumen, expertise, and ability to thoroughly work-up a case from beginning to end.
B — Overall structure and presentation has minimal organizational, grammatical, or spelling errors and is of professional quality.

SCORING RULES:
- Total possible: 420 points | Passing threshold: 70% = 294 points
- Any section scoring 0 automatically fails the paper
- Both Overall Impressions A and B must be Yes
- Word count must not exceed 19,000 words
- Formatting violations: 5-point deduction each (1. PDF format; 2. Times/Arial/Calibri/Helvetica font size 11-12; 3. Labs/Tables/Figures at end in chronological order)
- estimated_total = sum of (score * max_pts / 4) for each section minus formatting_deductions
"""

CS_RUBRIC = """CASE SUMMARY RUBRIC — score each section 0-4 pts.

TITLE (max 10 pts):
4 — Title accurately describes the contents of the case summary
2 — Title somewhat describes the contents of the case summary
0 — Title does not accurately describe the contents of the case summary

INTRODUCTION (max 20 pts):
4 — Complete, concise, and thorough description of pathophysiology, typical history/presentation, differential diagnoses, and diagnostic approach
3 — Mostly complete. 1-2 significant omissions.
2 — Somewhat complete. >2 significant omissions.
1 — Minimal description. Many significant omissions.
0 — Description of pathophysiology, typical history/presentation, differential diagnoses, and diagnostic approach are incomplete or missing.

TREATMENT / MANAGEMENT / PROGNOSIS (max 80 pts):
4 — Complete synopsis of treatment and management options for the clinical problem/diagnosis, and current recommended therapies/procedures.
3 — Mostly complete. 1-2 significant omissions.
2 — Somewhat complete. >2 significant omissions.
1 — Minimal synopsis. Several significant omissions.
0 — Synopsis of treatment/management options are incomplete or missing. Recommended therapies/procedures are not current or missing.

CASE HISTORY & PRESENTATION (max 80 pts):
4 — Complete brief description of the patient/population, chief complaint, and relevant history and clinical findings.
3 — Mostly complete. 1-2 significant omissions.
2 — Somewhat complete. >2 significant omissions.
1 — Minimal description. Many significant omissions.
0 — Description of patient/population, chief complaint, and relevant history/clinical findings are incomplete or missing.

CASE MANAGEMENT & OUTCOME (max 80 pts):
4 — All relevant procedures, medications, complications, comorbidities, and justification for deviations from standard procedure discussed. Full outcome including patient/case outcome, results of procedures/medical management, and full follow-up.
3 — Mostly complete. 1-2 significant omissions.
2 — Somewhat complete. >2 significant omissions.
1 — Very few relevant items discussed. Several significant omissions.
0 — Relevant procedures, medications, complications, co-morbidities, justification for deviations are incomplete or missing. Patient/case outcome, results, and follow-up are incomplete or missing.

DISCUSSION & CRITIQUE (max 100 pts):
4 — Constructive evaluation of case deficiencies, mistakes, and/or complications. Identifies potential changes for future cases. Demonstrates ability to learn from an imperfect case. No new material added.
3 — Mostly constructive. 1-2 significant omissions.
2 — Somewhat constructive. >2 significant omissions.
1 — Minimal constructive evaluation. Many significant omissions.
0 — Does not critically evaluate deficiencies. Unable to identify changes. Does not demonstrate learning. Significant new material added.

REFERENCES & ENDNOTES (max 10 pts):
4 — At least 1 but no more than 3 references from available literature, preferably peer-reviewed (well-regarded textbooks may be included)
2 — References listed but more current/applicable/specific references are readily available
0 — No references, more than 3 references, or inappropriate references used

LAB DATA & IMAGING (max 20 pts):
4 — Lab results labeled, legible, relevant to the case, and in chronological order
2 — Lab results present but not entirely relevant or could be more clearly displayed/described
0 — Lab results not labeled, illegible, not relevant, and/or not in chronological order

OVERALL IMPRESSIONS (Pass/Fail — a "No" on either fails the entire paper):
A — Case demonstrates management commensurate with ABVP diplomate level of practice: clinical acumen, expertise, and ability to thoroughly work-up a case from beginning to end.
B — Overall structure and presentation has minimal organizational, grammatical, or spelling errors and is of professional quality. Effectively communicates all relevant case information in a succinct manner.

SCORING RULES:
- Total possible: 400 points | Passing threshold: 70% = 280 points
- Any section scoring 0 automatically fails the paper
- Both Overall Impressions A and B must be Yes
- Word count must be 1,700-2,000 words (excludes tables, lab results, images, references, endnotes, section headings)
- Formatting violations: 5-point deduction each (1. PDF format; 2. Times/Arial/Calibri/Helvetica font size 11-12; 3. Labs/Tables/Figures at end in chronological order)
- estimated_total = sum of (score * max_pts / 4) for each section minus formatting_deductions
"""
