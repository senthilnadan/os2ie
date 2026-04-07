"""
W1 — Adversarial Synthesis

Tests whether the model can hold two opposing views simultaneously and produce
a nuanced synthesis without collapsing to one side.

Segments:
  1. build_case   → milestone: case_for, case_against
  2. stress_test  → milestone: weaknesses, steelmanned
  3. verdict      → milestone: synthesis, verdict

Input key: topic (str)
"""
from demo.lib.prompting import build_tool_provider

INPUT_KEY = "topic"

DSTT = {
    "segments": [
        {
            "transitions": [
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_argue_for", "topic"],
                    "outputs": ["case_for"],
                },
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_argue_against", "topic"],
                    "outputs": ["case_against"],
                },
            ],
            "milestone": ["case_for", "case_against"],
        },
        {
            "transitions": [
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_weaknesses", "case_for", "case_against"],
                    "outputs": ["weaknesses"],
                },
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_steelman", "case_against", "weaknesses"],
                    "outputs": ["steelmanned"],
                },
            ],
            "milestone": ["weaknesses", "steelmanned"],
        },
        {
            "transitions": [
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_synthesise", "case_for", "steelmanned"],
                    "outputs": ["synthesis"],
                },
                {
                    "tool": "asktemplate",
                    "inputs": ["_t_verdict", "synthesis", "weaknesses"],
                    "outputs": ["verdict"],
                },
            ],
            "milestone": ["synthesis", "verdict"],
        },
    ]
}

TEMPLATES = {
    "_t_argue_for": (
        "You are a skilled advocate. Present the strongest possible case FOR the "
        "following position. Be specific, use concrete reasoning, and give at least "
        "3 distinct arguments.\n\n"
        "Position: {{0}}\n\n"
        "Case for:"
    ),
    "_t_argue_against": (
        "You are a skilled advocate. Present the strongest possible case AGAINST the "
        "following position. Be specific, use concrete reasoning, and give at least "
        "3 distinct arguments.\n\n"
        "Position: {{0}}\n\n"
        "Case against:"
    ),
    "_t_weaknesses": (
        "You are a critical analyst. Given two opposing arguments, identify the top 3 "
        "weaknesses in EACH. Be specific — name which argument the weakness belongs to.\n\n"
        "Argument FOR:\n{{0}}\n\n"
        "Argument AGAINST:\n{{1}}\n\n"
        "Weaknesses:"
    ),
    "_t_steelman": (
        "You are a philosophical editor. Rewrite the argument below to address its "
        "identified weaknesses. Make it as strong as possible without changing its "
        "core position.\n\n"
        "Original argument:\n{{0}}\n\n"
        "Weaknesses to address:\n{{1}}\n\n"
        "Strengthened argument:"
    ),
    "_t_synthesise": (
        "You are a balanced analyst. Write a nuanced synthesis of the two arguments "
        "below. Acknowledge the strongest points of each side. Do not collapse to "
        "either position — identify the conditions under which each would be correct.\n\n"
        "Case for:\n{{0}}\n\n"
        "Strengthened case against:\n{{1}}\n\n"
        "Synthesis:"
    ),
    "_t_verdict": (
        "Given the synthesis and the weaknesses identified, write a final verdict in "
        "2-3 sentences: under what conditions is each side correct?\n\n"
        "Synthesis:\n{{0}}\n\n"
        "Weaknesses:\n{{1}}\n\n"
        "Verdict:"
    ),
}
