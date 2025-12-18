from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from conversation_manager import ConversationManager
import os

app = FastAPI()
manager = ConversationManager()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- TEMPLATES ----------------
templates = Jinja2Templates(directory="templates")

# Static files (serve images/css/js)
# Preferred: keep files in a dedicated 'static' folder next to this main.py
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------- MODELS ----------------
class ChatMessage(BaseModel):
    session_id: str
    message: str

class ResetModel(BaseModel):
    session_id: str

# ---------------- FRONTEND ----------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "chat.html",
        {"request": request}
    )

# ---------------- CHAT ----------------
@app.post("/chat")
def chat(data: ChatMessage):
    sid = data.session_id
    msg = data.message.strip()

    if not msg:
        return {"type": "error", "response": "Empty message"}

    if sid not in manager.sessions:
        manager.start_session(sid)

    # ✅ STEP 1: ADD USER MESSAGE
    manager.add_user(sid, msg)

    # ✅ STEP 2: HARD RULE-BASED DIRECT ANSWERS
    if (
        manager.is_direct_knowledge_question(msg)
        or manager.is_program_or_fee_question(msg)
        or manager.is_logistics_or_registration_question(msg)
    ):
        answer = manager.final_answer(sid)
        manager.add_assistant(sid, answer)
        return {"type": "final_answer", "response": answer}

    # ✅ STEP 3: LLM DECIDES FOLLOW-UP
    if not manager.needs_follow_up(sid):
        answer = manager.final_answer(sid)
        manager.add_assistant(sid, answer)
        return {"type": "final_answer", "response": answer}

    # ✅ STEP 4: FOLLOW-UP LIMIT
    if manager.should_finalize(sid):
        answer = manager.final_answer(sid)
        manager.add_assistant(sid, answer)
        return {"type": "final_answer", "response": answer}

    # ✅ STEP 5: ASK FOLLOW-UP
    followup = manager.generate_followup(sid)
    manager.add_assistant(sid, followup)

    return {"type": "follow_up_question", "response": followup}

# ---------------- RESET ----------------
@app.post("/reset")
def reset(data: ResetModel):
    manager.reset_session(data.session_id)
    return {"status": "cleared", "session_id": data.session_id}
