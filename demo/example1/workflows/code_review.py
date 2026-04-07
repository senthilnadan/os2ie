"""
W3 — Iterative Code Review

Tests whether the model can separate intent analysis from code analysis,
merge them into prioritised issues, and produce verifiable fix suggestions.

Segments:
  1. understand → milestone: intent, code_analysis
  2. diagnose   → milestone: issues, prioritised_issues
  3. prescribe  → milestone: reviewed_code

Input key: code (str)
"""
from demo.lib.prompting import build_tool_provider

INPUT_KEY = "code"

DSTT = {
    "segments": [
        {
            "transitions": [
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_intent", "code"],
                    "outputs": ["intent"],
                },
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_code_analysis", "code"],
                    "outputs": ["code_analysis"],
                },
            ],
            "milestone": ["intent", "code_analysis"],
        },
        {
            "transitions": [
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_find_issues", "intent", "code_analysis"],
                    "outputs": ["issues"],
                },
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_prioritise", "issues"],
                    "outputs": ["prioritised_issues"],
                },
            ],
            "milestone": ["issues", "prioritised_issues"],
        },
        {
            "transitions": [
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_suggest_fixes", "prioritised_issues", "code"],
                    "outputs": ["fix_suggestions"],
                },
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_verify_logic", "fix_suggestions", "intent"],
                    "outputs": ["reviewed_code"],
                },
            ],
            "milestone": ["reviewed_code"],
        },
    ]
}

TEMPLATES = {
    "_t_intent": (
        "Read the following code and infer its intended purpose in 2-3 sentences. "
        "Focus on what it is supposed to do, not what it actually does.\n\n"
        "Code:\n{{0}}\n\n"
        "Inferred intent:"
    ),
    "_t_code_analysis": (
        "Analyse the following code. Describe precisely what it actually does, "
        "step by step. Be technical and specific — do not infer intent.\n\n"
        "Code:\n{{0}}\n\n"
        "Code analysis:"
    ),
    "_t_find_issues": (
        "Given the inferred intent and the actual code analysis below, list every "
        "issue where the code fails to achieve its intent, contains bugs, or has "
        "quality problems. Give each issue a one-line description.\n\n"
        "Intent:\n{{0}}\n\n"
        "Code analysis:\n{{1}}\n\n"
        "Issues found:"
    ),
    "_t_prioritise": (
        "Sort the following code issues by severity. Use exactly these labels:\n"
        "  CRITICAL — breaks functionality or produces wrong results\n"
        "  MAJOR    — degrades reliability, safety, or maintainability\n"
        "  MINOR    — style, naming, or optimisation\n\n"
        "Keep one issue per line. Format: [LABEL] description\n\n"
        "Issues:\n{{0}}\n\n"
        "Prioritised issues:"
    ),
    "_t_suggest_fixes": (
        "For every CRITICAL and MAJOR issue below, suggest a concrete fix. "
        "Show the corrected code snippet for each fix. Label each fix with the "
        "issue it addresses.\n\n"
        "Prioritised issues:\n{{0}}\n\n"
        "Original code:\n{{1}}\n\n"
        "Fix suggestions:"
    ),
    "_t_verify_logic": (
        "Given the fix suggestions and the original intent, verify that applying "
        "all suggested fixes would fully satisfy the intent. List any remaining "
        "gaps. If none, state: 'All issues resolved.'\n\n"
        "Fix suggestions:\n{{0}}\n\n"
        "Original intent:\n{{1}}\n\n"
        "Verification:"
    ),
}
