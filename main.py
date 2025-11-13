import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="AI Minor Project API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AssessmentRequest(BaseModel):
    text: str = Field(..., min_length=10, description="User journal or symptoms description")


class AssessmentResult(BaseModel):
    score: float
    label: str
    keywords: List[str]
    created_at: datetime
    id: Optional[str] = None


def simple_stress_model(text: str) -> AssessmentResult:
    """
    Lightweight rule-based classifier for demo purposes.
    Scores presence of stress/depression/anxiety keywords and assigns a label.
    """
    stress_kw = {
        "stress": 2,
        "stressed": 2,
        "overwhelmed": 2,
        "pressure": 1.5,
        "tired": 1,
        "exhausted": 1.5,
        "burnout": 2,
        "workload": 1,
    }
    anxiety_kw = {
        "anxious": 2,
        "worry": 1.5,
        "panic": 2,
        "nervous": 1,
        "fear": 1.5,
        "uneasy": 1,
    }
    mood_kw = {
        "sad": 1.5,
        "down": 1,
        "depressed": 2,
        "hopeless": 2,
        "insomnia": 1.5,
        "sleep": 0.5,
        "headache": 0.5,
    }

    text_l = text.lower()
    matched = []
    score = 0.0

    for kw, w in {**stress_kw, **anxiety_kw, **mood_kw}.items():
        if kw in text_l:
            matched.append(kw)
            score += w

    # Normalize score roughly by length
    length_penalty = min(1.0, max(0.5, 100 / (len(text) + 1)))
    score = round(score * length_penalty, 2)

    if score >= 6:
        label = "High"
    elif score >= 3:
        label = "Moderate"
    elif score > 0:
        label = "Low"
    else:
        label = "Minimal"

    return AssessmentResult(score=score, label=label, keywords=matched, created_at=datetime.utcnow())


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        from database import db
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


@app.post("/api/assess", response_model=AssessmentResult)
def assess_text(req: AssessmentRequest):
    """Assess stress level from free-text description and store the result."""
    result = simple_stress_model(req.text)
    # Persist to DB if available
    try:
        from database import create_document
        doc_id = create_document("assessments", {
            "text": req.text,
            "score": result.score,
            "label": result.label,
            "keywords": result.keywords,
            "created_at": result.created_at,
        })
        result.id = doc_id
    except Exception:
        # DB not available; continue without persistence
        pass
    return result


@app.get("/api/history")
def get_history(limit: int = 10):
    """Return recent assessment history if database is connected."""
    try:
        from database import get_documents
        docs = get_documents("assessments", {}, limit=limit)
        def clean(doc):
            doc["id"] = str(doc.get("_id"))
            doc.pop("_id", None)
            return doc
        return [clean(d) for d in docs]
    except Exception:
        return []


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
