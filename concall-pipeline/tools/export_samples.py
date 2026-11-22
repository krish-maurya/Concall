"""Dump every stored summary to samples/<company>/{summary.json,summary.md}."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db, config
db.init()
for r in db.list_all():
    row = db.get(r["id"]); d = f"samples/{re.sub(r'[^A-Za-z0-9]+','_',row['company'])}_{row['quarter']}".replace(" ", "")
    os.makedirs(d, exist_ok=True)
    open(f"{d}/summary.json", "w", encoding="utf-8").write(
        json.dumps(json.loads(row["json"]), indent=2, ensure_ascii=False)
    )
    open(f"{d}/summary.md", "w", encoding="utf-8").write(row["md"])
    t = os.path.join(os.path.dirname(config.DB_PATH) or ".", "transcripts", f"{r['id']}.txt")
    if os.path.exists(t): open(f"{d}/transcript.txt", "w", encoding="utf-8").write(open(t, encoding="utf-8").read())
    print("wrote", d)
