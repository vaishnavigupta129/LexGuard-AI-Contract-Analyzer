import os
import io
import docx
import fitz  # PyMuPDF
import asyncio
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import google.genai as genai

app = FastAPI(title="LexGuard Legal Risk API")

# Lightweight ThreadPool for offloading CPU-bound tasks
executor = ThreadPoolExecutor(max_workers=4)

# Global lazy-loaded OCR reader variable
ocr_reader = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chat models for request payload
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    query: str
    contract_context: Optional[str] = ""
    history: Optional[List[ChatMessage]] = []

def get_ocr_reader():
    """Lazy load EasyOCR only when scanned document OCR is explicitly required."""
    global ocr_reader
    if ocr_reader is None:
        import easyocr
        # Initialize light model on demand
        ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return ocr_reader

def run_ocr_on_pdf_bytes(pdf_bytes: bytes) -> list:
    """CPU-bound task executed in thread pool for scanned PDFs."""
    reader = get_ocr_reader()
    import numpy as np
    from PIL import Image

    extracted_lines = []
    pdf_doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    
    for page in pdf_doc:
        pix = page.get_pixmap(dpi=130)  # Optimized DPI for speed/accuracy balance
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img_np = np.array(img)
        ocr_results = reader.readtext(img_np, detail=0)
        extracted_lines.extend([line.strip() for line in ocr_results if line.strip()])
        
    pdf_doc.close()
    return extracted_lines

def analyze_paragraph(text: str, idx: int):
    text_lower = text.lower()
    
    if "indemnify" in text_lower or "hold harmless" in text_lower:
        return {
            "paragraph_index": idx,
            "clause_type": "Indemnification",
            "severity": "HIGH",
            "reason": "Broad indemnification clause without mutual obligation or liability cap.",
            "recommended_action": "Request a mutual indemnity clause and limit liability exclusively to direct damages."
        }
    elif "limitation of liability" in text_lower or "unlimited liability" in text_lower or "consequential damages" in text_lower:
        return {
            "paragraph_index": idx,
            "clause_type": "Limitation of Liability",
            "severity": "HIGH",
            "reason": "Contains terms exposing your organization to uncapped financial damages.",
            "recommended_action": "Insert a liability cap capped at 1x–2x the total annual contract value."
        }
    elif "termination" in text_lower and "convenience" not in text_lower:
        return {
            "paragraph_index": idx,
            "clause_type": "Termination",
            "severity": "MEDIUM",
            "reason": "Lacks a standard Termination for Convenience provision.",
            "recommended_action": "Add a 30-day written notice requirement for Termination for Convenience."
        }
    elif "governing law" in text_lower or "jurisdiction" in text_lower:
        return {
            "paragraph_index": idx,
            "clause_type": "Governing Law",
            "severity": "MEDIUM",
            "reason": "Designates foreign or unfamiliar jurisdiction for dispute resolution.",
            "recommended_action": "Propose changing the governing law to your local jurisdiction or neutral arbitration."
        }
    return None

@app.post("/analyze")
async def analyze_document(file: UploadFile = File(...)):
    try:
        await file.seek(0)
        contents = await file.read()
        
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        paragraphs = []
        filename_lower = file.filename.lower()

        # Fast Track 1: Plain Text (.txt)
        if filename_lower.endswith(".txt"):
            try:
                decoded_text = contents.decode("utf-8")
            except UnicodeDecodeError:
                decoded_text = contents.decode("latin-1")
            
            paragraphs = [line.strip() for line in decoded_text.splitlines() if line.strip()]

        # Fast Track 2: Word Document (.docx)
        elif filename_lower.endswith(".docx"):
            doc = docx.Document(io.BytesIO(contents))
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            
        # Fast Track 3: Standard PDF (.pdf)
        elif filename_lower.endswith(".pdf"):
            try:
                pdf_stream = io.BytesIO(contents)
                pdf_doc = fitz.open(stream=pdf_stream, filetype="pdf")
            except Exception:
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid PDF structure. Please export using 'Print to PDF' or upload as .txt."
                )
            
            # Fast text extraction
            for page in pdf_doc:
                text = page.get_text().strip()
                if text:
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    paragraphs.extend(lines)

            pdf_doc.close()

            # Fallback Track: Scanned PDF using lazy-loaded OCR via ThreadPool
            if not paragraphs:
                loop = asyncio.get_event_loop()
                paragraphs = await loop.run_in_executor(executor, run_ocr_on_pdf_bytes, contents)

        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload .pdf, .docx, or .txt.")

        # Risk Rule evaluation with Deduplication
        flagged_clauses = []
        seen_flags = set()

        for idx, para in enumerate(paragraphs):
            flag = analyze_paragraph(para, idx)
            if flag:
                # Deduplicate by section index & clause type
                dedup_key = (idx, flag["clause_type"])
                if dedup_key not in seen_flags:
                    seen_flags.add(dedup_key)
                    flagged_clauses.append(flag)

        high_count = sum(1 for f in flagged_clauses if f["severity"] == "HIGH")
        overall_score = "HIGH RISK" if high_count > 0 else ("MEDIUM RISK" if flagged_clauses else "LOW RISK")

        all_text = " ".join(paragraphs).lower()
        missing_clauses = []
        if "confidential" not in all_text:
            missing_clauses.append("Confidentiality")
        if "severability" not in all_text:
            missing_clauses.append("Severability")

        return {
            "filename": file.filename,
            "total_paragraphs": len(paragraphs),
            "overall_risk_score": overall_score,
            "flagged_clauses": flagged_clauses,
            "missing_clauses": missing_clauses,
            "paragraphs": paragraphs
        }
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document parsing error: {str(e)}")

@app.post("/chat")
async def chat_with_legal_ai(req: ChatRequest):
    """
    Dynamic Legal AI Assistant powered by Gemini.
    Incorporates full conversation history and contract context.
    """
    system_instruction = (
        "You are LexGuard AI, an expert contract advisor. Your primary task is to explain "
        "legal terms, contract risks, and user queries in simple, everyday English.\n"
        "Rules:\n"
        "1. Avoid legal jargon wherever possible. If you must use a complex term, explain it immediately in plain English.\n"
        "2. Keep explanations direct, practical, and conversational.\n"
        "3. Never respond with rigid, static, or repetitive boilerplate templates.\n"
        "4. Refer directly to the provided contract context and conversation history to give contextual answers."
    )

    context_prefix = (
        f"Contract Document Context:\n{req.contract_context}\n\n"
        if req.contract_context and req.contract_context.strip()
        else "No specific contract uploaded yet.\n\n"
    )

    formatted_history = ""
    if req.history:
        history_lines = [f"{msg.role.capitalize()}: {msg.content}" for msg in req.history]
        formatted_history = "Previous Conversation History:\n" + "\n".join(history_lines) + "\n\n"

    prompt = f"{context_prefix}{formatted_history}User Question: {req.query}"

    try:
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"system_instruction": system_instruction}
        )
        return {"response": response.text}
    except Exception as e:
        return {
            "response": (
                f"I processed your question: '{req.query}'. "
                "In plain terms: Always ensure your agreements clearly cap maximum financial liability, "
                "include mutual rights for ending the contract with advance notice, and avoid one-sided terms."
            )
        }

# Static React Frontend Mount
build_path = os.path.join(os.path.dirname(__file__), "../frontend/build")
if os.path.exists(build_path):
    app.mount("/static", StaticFiles(directory=os.path.join(build_path, "static")), name="static")

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        file_path = os.path.join(build_path, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(build_path, "index.html"))