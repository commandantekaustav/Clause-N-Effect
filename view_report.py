import json
import os

# Read the generated report
report_path = "report.json"
if not os.path.exists(report_path):
    print(f"❌ Error: {report_path} not found! Run 'pyright --outputjson > report.json' first.")
    exit(1)

with open(report_path, "r", encoding="utf-16") as f:
    data = json.load(f)

diagnostics = data.get("generalDiagnostics", [])
summary = data.get("summary", {})

# 1. Print a clean summary to the console
print("\n" + "="*40)
print("📋 PYRIGHT ANALYSIS SUMMARY")
print("="*40)
print(f"Total Files Scanned: {summary.get('filesAnalyzed', 0)}")
print(f"🔴 Total Errors:     {summary.get('errorCount', 0)}")
print(f"🟡 Total Warnings:   {summary.get('warningCount', 0)}")
print("="*40 + "\n")

# 2. Write details to a clean Markdown file
with open("Pyright_Report.md", "w", encoding="utf-8") as out:
    out.write("# 📋 Pyright Quality Report\n\n")
    out.write(f"**Total Files Checked:** {summary.get('filesAnalyzed', 0)}  \n")
    out.write(f"**Total Errors:** {summary.get('errorCount', 0)}  \n")
    out.write(f"**Total Warnings:** {summary.get('warningCount', 0)}  \n\n")
    out.write("## 🔍 Issue Details\n\n")
    out.write("| File | Line | Severity | Message |\n")
    out.write("| --- | --- | --- | --- |\n")
    
    for d in diagnostics:
        # Clean up absolute paths to show relative paths
        file = d.get('file', 'Unknown')
        if "Clause-N-Effect" in file:
            file = file.split("Clause-N-Effect")[-1].lstrip("\\/")
            
        line = d.get('range', {}).get('start', {}).get('line', 0) + 1
        sev = d.get('severity', 'info').upper()
        msg = d.get('message', '').replace("\n", " ")
        
        # Format severity emojis for easier reading
        sev_display = f"🔴 {sev}" if sev == "ERROR" else f"🟡 {sev}"
        out.write(f"| {file} | {line} | {sev_display} | {msg} |\n")

print("✨ Comprehensive markdown report saved to: Pyright_Report.md")
