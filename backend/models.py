from sqlalchemy import Column, Integer, String, DateTime, JSON
import datetime
from backend.database import Base

class ContractAudit(Base):
    __tablename__ = "contract_audits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)
    overall_risk_score = Column(String(50), nullable=False)
    total_paragraphs = Column(Integer, nullable=False)
    flagged_clauses = Column(JSON, nullable=False)
    missing_clauses = Column(JSON, nullable=False)