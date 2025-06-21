import os
import re
from collections import defaultdict

# Root folder to scan
ROOT = "./kubernetes"

# File extensions to check
EXTENSIONS = (".yaml", ".yml")

# Paths to exclude (partial match anywhere in path)
EXCLUDE_DIRS = [".private", ".venv", "docker", "talos"]

# Regex for schema lines
SCHEMA_RE = re.compile(r"#\s*yaml-language-server:\s*\$schema=(.*)")

schema_usage = defaultdict(list)
missing_schema_files = set()

def should_exclude(path):
    return any(part in path for part in EXCLUDE_DIRS)

for dirpath, _, filenames in os.walk(ROOT):
    for filename in filenames:
        if not filename.endswith(EXTENSIONS):
            continue

        filepath = os.path.join(dirpath, filename)
        if should_exclude(filepath):
            continue

        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()

        doc_has_schema = False
        doc_started = False
        any_schema_found = False

        for line in lines:
            if line.strip() == "---":
                if not doc_has_schema and doc_started:
                    pass  # Allow partial coverage
                doc_has_schema = False
                doc_started = True
                continue

            match = SCHEMA_RE.match(line)
            if match:
                schema = match.group(1).strip()
                schema_usage[schema].append(filepath)
                doc_has_schema = True
                any_schema_found = True

        if not any_schema_found:
            missing_schema_files.add(filepath)

# Print schema usage with associated files
print("\n📘 Schema Usage by File:")
for schema, files in sorted(schema_usage.items()):
    print(f"\n🔗 {schema}")
    for f in sorted(set(files)):
        print(f"   • {f}")

# Print missing files
if missing_schema_files:
    print("\n⚠️  Files Missing Schema:")
    for f in sorted(missing_schema_files):
        print(f"   • {f}")
else:
    print("\n✅ All files include schema annotations.")

# Print alphabetically sorted list of unique schemas
print("\n📚 Alphabetical List of Unique Schemas Used:")
for schema in sorted(schema_usage):
    print(f" - {schema}")
