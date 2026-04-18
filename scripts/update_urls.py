import os
import re
script_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(script_dir, '..', 'frontend', 'src')

for root, _, files in os.walk(frontend_dir):
    for file in files:
        if file.endswith((".ts", ".tsx")):
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # For double quotes: "http://127.0.0.1:8000/..." -> `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/...`
            content = re.sub(r'"http://127\.0\.0\.1:8000([^"]*)"', r'`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}\1`', content)
            
            # For single quotes: 'http://127.0.0.1:8000/...' -> `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/...`
            content = re.sub(r"'http://127\.0\.0\.1:8000([^']*)'", r"`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}\1`", content)
            
            # For backticks (template literals): `http://127.0.0.1:8000/...` -> `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/...`
            # This one we just replace the prefix inside the existing backticks since it's already a template literal!
            content = content.replace("`http://127.0.0.1:8000", "`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}")

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

print("Updated URLs successfully.")
