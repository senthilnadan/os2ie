"""
W2 — Deep Research Report

Tests whether the model can decompose a hard question, answer sub-parts
independently, detect its own contradictions, and produce a coherent report.

Segments:
  1. decompose    → milestone: sub_questions
  2. investigate  → milestone: answers, contradictions
  3. report       → milestone: report

Input key: question (str)
"""
from demo.lib.prompting import build_tool_provider

INPUT_KEY = "question"

DSTT = {
    "segments": [
        {
            "transitions": [
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_decompose", "question"],
                    "outputs": ["sub_questions"],
                },
            ],
            "milestone": ["sub_questions"],
        },
        {
            "transitions": [
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_answer_each", "sub_questions"],
                    "outputs": ["answers"],
                },
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_cross_check", "sub_questions", "answers"],
                    "outputs": ["contradictions"],
                },
            ],
            "milestone": ["answers", "contradictions"],
        },
        {
            "transitions": [
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_resolve", "answers", "contradictions"],
                    "outputs": ["resolved"],
                },
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_summarise", "resolved"],
                    "outputs": ["summary"],
                },
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_format", "summary"],
                    "outputs": ["report"],
                },
            ],
            "milestone": ["report"],
        },
    ]
}

TEMPLATES = {
    "_t_decompose": (
        "Break the following question into 3-5 focused sub-questions that together "
        "would fully answer it. Each sub-question must have exactly one clear, "
        "specific answer.\n\n"
        "Question: {{0}}\n\n"
        "Sub-questions (numbered list):"
    ),
    "_t_answer_each": (
        "Answer each sub-question below concisely and directly. Label each answer "
        "with its sub-question number.\n\n"
        "Sub-questions:\n{{0}}\n\n"
        "Answers:"
    ),
    "_t_cross_check": (
        "Given the sub-questions and answers below, identify any contradictions, "
        "inconsistencies, or gaps between the answers. Be specific about which "
        "answers conflict. If none exist, state exactly: 'No contradictions found.'\n\n"
        "Sub-questions:\n{{0}}\n\n"
        "Answers:\n{{1}}\n\n"
        "Contradictions and gaps:"
    ),
    "_t_resolve": (
        "Given the answers and any contradictions identified, produce a resolved, "
        "coherent set of findings. Where contradictions exist, state which answer "
        "is more defensible and why.\n\n"
        "Answers:\n{{0}}\n\n"
        "Contradictions:\n{{1}}\n\n"
        "Resolved findings:"
    ),
    "_t_summarise": (
        "Summarise the following findings into a coherent narrative of 3-5 sentences. "
        "Write for a technical reader.\n\n"
        "Findings:\n{{0}}\n\n"
        "Summary:"
    ),
    "_t_format": (
        "Format the summary below as a concise research report with exactly three "
        "parts:\n"
        "HEADLINE: one sentence stating the core finding\n"
        "BODY: the summary as-is\n"
        "KEY INSIGHT: one sentence — the single most actionable takeaway\n\n"
        "Summary:\n{{0}}\n\n"
        "Report:"
    ),
}
