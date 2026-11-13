"""Deterministic prompts for gaps already identified during reconstruction."""
import re


def prompt_for(claim):
    text = claim['text'].strip()
    if re.search(r'\b(who|owner|owns|ownership|responsible)\b', text, re.I):
        return text, 'Who will own this work, and where can the successor reach them or find the handover notes?'
    if re.search(r'\b(when|deadline|date|schedule|frequency)\b', text, re.I):
        return text, 'What date or schedule should the successor use, and where can they verify it?'
    if re.search(r'\b(how|run|deploy|configure|setup|procedure)\b', text, re.I):
        return text, 'What concrete step should the successor take, and where are the instructions?'
    return text, 'What specific detail can you confirm, and where can the successor check it?'


def follow_up(claim, answer, uncertain=False):
    words = re.findall(r"\b[\w'-]+\b", answer)
    vague = re.search(r"\b(not sure|unknown|no idea|don't know|do not know|tbd|maybe)\b", answer, re.I)
    if uncertain or vague or len(words) < 6:
        return prompt_for(claim)[1]
    return None
