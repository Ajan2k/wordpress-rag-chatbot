import sys
import os

# add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.rag_orchestrator import RAGOrchestrator

rag = RAGOrchestrator()
rag.answer("test")
