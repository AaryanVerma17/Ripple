"""What-if chat: reads a sentence, runs the real analysis, and answers from the result."""
from __future__ import annotations

from . import ai, store
from .analysis import analyze_change
from .dataset import get_dataset
from .intent import llm_intent, parse_intent
from .resolve import ChangeError
from .schemas import ChangeRequest, ChatRequest
from .validator import validate_report

EXAMPLES = ["What if the motor is 24 V?", "What if I swap the battery for BAT-ALT-24?", "What if the chassis is 0.5 kg lighter?",
            "What if the battery capacity doubles?", "What if the controller costs $30?"]
HELP = ("I can run a what-if on any part, or answer questions about the last analysis. Name a part and a new value or a "
        "catalogue part, for example: ")


async def handle_chat(req: ChatRequest) -> dict:
    data = get_dataset()
    report = store.get_analysis(req.analysis_id) if req.analysis_id else None
    intent = await llm_intent(req.message, data, req.context_entity_id)
    source = "model" if intent else "rules"
    if intent is None:
        intent = parse_intent(req.message, data, req.context_entity_id)
    kind = intent["kind"]

    if kind == "change":
        try:
            change = ChangeRequest(**intent["request"], reason=req.message[:300], kind="whatif")
            new = analyze_change(change)
        except (ChangeError, ValueError) as e:
            return {"kind": "error", "reply": str(e), "suggestions": EXAMPLES[:3], "reading": intent.get("reading"), "reading_source": source}
        new["validation"] = validate_report(new, data)
        new["ai_synthesis"] = await ai.synthesize(new, data)
        store.save_analysis(new, kind="whatif")
        body = ai.narrate(new).split("\n", 2)[2]  # the reading line below already says what changed
        reply = f"**{intent['reading']}**\n\n{body}"
        if new["ai_synthesis"]["status"] == "completed":
            reply += "\n\n" + new["ai_synthesis"]["summary"]
        return {"kind": "analysis", "reply": reply, "analysis_id": new["analysis_id"], "card": ai.card(new),
                "reading": intent["reading"], "reading_source": source,
                "suggestions": ["Why did that fail?", "What does it cost?", "What are my options to fix it?", "Which tests do I need to re-run?"]}

    if kind == "clarify":
        return {"kind": "clarify", "reply": intent["message"], "options": intent.get("options", []), "suggestions": EXAMPLES[:3]}

    if kind == "question":
        if not report:
            return {"kind": "help", "reply": "Run a what-if or an analysis first, then ask me about it. " + HELP + EXAMPLES[0], "suggestions": EXAMPLES[:3]}
        text = await ai.answer_llm(req.message, report, data) or ai.answer_offline(req.message, report, data)
        if text:
            return {"kind": "answer", "reply": text, "analysis_id": report["analysis_id"],
                    "suggestions": ["What does it cost?", "What are my options to fix it?", "What data is missing?"]}
        return {"kind": "help", "reply": "I couldn't answer that from this analysis. Try asking about cost, tests, fixes, missing data or why something failed.",
                "suggestions": ["What does it cost?", "Which tests do I need to re-run?", "What data is missing?"]}

    if report:  # no change found in the sentence: maybe it's a question ("what does it cost?")
        text = await ai.answer_llm(req.message, report, data) or ai.answer_offline(req.message, report, data)
        if text:
            return {"kind": "answer", "reply": text, "analysis_id": report["analysis_id"],
                    "suggestions": ["Why did that fail?", "What are my options to fix it?", "What data is missing?"]}
    return {"kind": "help", "reply": HELP + EXAMPLES[0], "suggestions": EXAMPLES[:4]}
