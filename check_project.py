"""Run:  py check_project.py   -> lists any template/static file the project needs but cannot find."""
import glob
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
missing = []


def need(path, why):
    if not os.path.exists(os.path.join(ROOT, path)):
        missing.append((path, why))


# every template that a route renders
for route_file in glob.glob(os.path.join(ROOT, "routes", "*.py")):
    text = open(route_file, encoding="utf-8").read()
    for name in re.findall(r'render_template\(\s*"([^"]+)"', text):
        need(os.path.join("templates", name), f"used in routes/{os.path.basename(route_file)}")

# templates that extend / import / include other templates
for tpl in glob.glob(os.path.join(ROOT, "templates", "**", "*.html"), recursive=True):
    text = open(tpl, encoding="utf-8").read()
    for name in re.findall(r'{%\s*(?:extends|include|import|from)\s+"([^"]+\.html)"', text):
        need(os.path.join("templates", name), f"used in {os.path.relpath(tpl, ROOT)}")
    for name in re.findall(r"filename='([^']+)'", text):
        need(os.path.join("static", name), f"used in {os.path.relpath(tpl, ROOT)}")

if missing:
    print("MISSING FILES:")
    for path, why in sorted(set(missing)):
        print("  -", path, f"({why})")
    print("\nCopy these files from the original zip into the same folders, then run this check again.")
else:
    print("All required template and static files were found.")
