
import sys
import os

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.nlq.sql_generator import generate_sql

test_cases = [
    {
        "query": "Show me districts with good road connectivity",
        "expected_level": "district",
        "expected_condition": "> 0.7"
    },
    {
        "query": "Show me areas with medium road connectivity",
        "expected_level": "block",
        "expected_condition": "BETWEEN 0.3 AND 0.7"
    },
    {
        "query": "blocks with poor road",
        "expected_level": "block",
        "expected_condition": "< 0.3"
    },
    {
        "query": "Show worst infrastructure blocks",
        "expected_level": "block",
        "expected_condition": "ORDER BY"
    }
]

print("Running NLQ Tests...\n")
failed = False

for test in test_cases:
    query = test["query"]
    result = generate_sql(query)
    
    print(f"Query: '{query}'")
    print(f"  -> Level: {result['level']}")
    
    # Check level
    if result["level"] != test["expected_level"]:
        print(f"  [FAIL] Expected level '{test['expected_level']}', got '{result['level']}'")
        failed = True
    else:
        print(f"  [PASS] Level matches")

    # Check SQL condition
    sql = result["sql"]
    if test["expected_condition"] in sql:
         print(f"  [PASS] SQL contains '{test['expected_condition']}'")
    else:
         print(f"  [FAIL] SQL missing '{test['expected_condition']}'")
         print(f"  SQL: {sql.strip()}")
         failed = True
         
    print("-" * 30)

if failed:
    print("\nSome tests FAILED.")
    sys.exit(1)
else:
    print("\nAll tests PASSED.")
