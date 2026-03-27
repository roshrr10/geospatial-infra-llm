import asyncio
import os
import sys

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.services.ollama_service import get_summary_from_llm

async def test_summary():
    question = "Which schools have both computers and smart classrooms?"
    # Mock data with a complex type (e.g. Decimal or custom serializable)
    mock_data = [
        {"schoolName": "TEST SCHOOL 1", "udiseCode": "123", "count": 10},
        {"schoolName": "TEST SCHOOL 2", "udiseCode": "456", "count": 20}
    ]
    
    print("Testing Summary Generation...")
    try:
        summary = await get_summary_from_llm(question, mock_data)
        print("\nSUMMARY RESULT:\n")
        print(summary)
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_summary())
