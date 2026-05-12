"""
FastAPI server for Support Triage Agent
Run with: uvicorn api_server:app --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from agent import SupportTriageAgent

# Initialize agent
agent = SupportTriageAgent()

# Create FastAPI app
app = FastAPI(
    title="Support Triage Agent API",
    description="Enterprise AI support ticket triage system with 18 intelligence features",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class TicketRequest(BaseModel):
    """Support ticket for triage"""
    issue: str = Field(..., description="Full problem description")
    subject: str = Field(..., description="Ticket subject/title")
    company: Optional[str] = Field(None, description="HackerRank, Claude, or Visa")

class TriageResponse(BaseModel):
    """Triage result"""
    ticket_id: Optional[str] = None
    status: str = Field(..., description="replied or escalated")
    priority: str = Field(..., description="P0_Critical, P1_High, P2_Medium, P3_Low")
    sentiment: str = Field(..., description="angry, frustrated, neutral, positive")
    confidence: float = Field(..., description="0.0-1.0")
    quality: float = Field(..., description="0.0-1.0")
    churn_risk: int = Field(..., description="0-100")
    health_score: int = Field(..., description="0-100")
    response: Optional[str] = None
    product_area: Optional[str] = None
    request_type: Optional[str] = None
    justification: str = Field(..., description="Why this decision was made")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class BatchRequest(BaseModel):
    """Batch of tickets for processing"""
    tickets: list[TicketRequest]

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: str

@app.get("/", tags=["health"])
async def root():
    """Root endpoint"""
    return {
        "name": "Support Triage Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "triage": "/triage",
            "batch": "/batch",
            "health": "/health",
            "dashboard": "/dashboard"
        }
    }

@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )

@app.post("/triage", response_model=TriageResponse, tags=["triage"])
async def triage_ticket(ticket: TicketRequest):
    """
    Triage a single support ticket
    
    Returns decision, response, and 18 intelligence signals
    """
    try:
        # Process ticket through agent
        result = agent.process({
            'issue': ticket.issue,
            'subject': ticket.subject,
            'company': ticket.company or 'unknown'
        })
        
        # Map to response model
        return TriageResponse(
            status=result.get('status', 'escalated'),
            priority=result.get('urgency', 'P3_Low'),
            sentiment=result.get('sentiment', 'neutral'),
            confidence=result.get('confidence', 0.0),
            quality=result.get('quality', 0.0),
            churn_risk=result.get('churn_risk', 0),
            health_score=result.get('health_score', 0),
            response=result.get('response'),
            product_area=result.get('product_area'),
            request_type=result.get('request_type'),
            justification=result.get('justification', '')
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch", tags=["triage"])
async def batch_triage(batch: BatchRequest):
    """
    Triage multiple tickets in one request
    
    Returns array of triage results
    """
    if not batch.tickets:
        raise HTTPException(status_code=400, detail="No tickets provided")
    
    if len(batch.tickets) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 tickets per batch")
    
    try:
        results = []
        for i, ticket in enumerate(batch.tickets):
            result = agent.process({
                'issue': ticket.issue,
                'subject': ticket.subject,
                'company': ticket.company or 'unknown'
            })
            
            results.append({
                'ticket_index': i,
                'status': result.get('status', 'escalated'),
                'priority': result.get('urgency', 'P3_Low'),
                'sentiment': result.get('sentiment', 'neutral'),
                'confidence': result.get('confidence', 0.0),
                'quality': result.get('quality', 0.0),
                'churn_risk': result.get('churn_risk', 0),
                'health_score': result.get('health_score', 0),
            })
        
        return {
            'total': len(batch.tickets),
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard", tags=["outputs"])
async def get_dashboard():
    """
    Serve the HTML dashboard
    """
    dashboard_path = 'output/dashboard.html'
    if not os.path.exists(dashboard_path):
        raise HTTPException(status_code=404, detail="Dashboard not found. Run agent first.")
    
    return FileResponse(dashboard_path, media_type="text/html")

@app.get("/stats", tags=["analytics"])
async def get_stats():
    """
    Get analytics statistics
    """
    stats_path = 'output/analytics_report.csv'
    if not os.path.exists(stats_path):
        raise HTTPException(status_code=404, detail="Stats not found. Run agent first.")
    
    # Parse CSV and return as JSON
    import csv
    results = []
    with open(stats_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)
    
    return {
        'total_tickets': len(results),
        'data': results
    }

@app.get("/faq", tags=["analytics"])
async def get_faq():
    """
    Get auto-generated FAQ
    """
    import json
    faq_path = 'output/faq/faq_entries.json'
    if not os.path.exists(faq_path):
        raise HTTPException(status_code=404, detail="FAQ not found. Run agent first.")
    
    with open(faq_path, 'r') as f:
        faq = json.load(f)
    
    return {
        'total_entries': len(faq),
        'entries': faq
    }

@app.post("/export", tags=["outputs"])
async def export_results(format: str = "csv"):
    """
    Export results in specified format
    """
    if format == "csv":
        output_path = 'output/output.csv'
        media_type = "text/csv"
    elif format == "json":
        import json
        output_path = 'output/output.json'
        if not os.path.exists(output_path):
            raise HTTPException(status_code=404, detail="JSON export not available")
        media_type = "application/json"
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")
    
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Output not found")
    
    return FileResponse(output_path, media_type=media_type)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
