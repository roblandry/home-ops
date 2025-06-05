#!/usr/bin/env python3
import yaml
import os
import subprocess
import shutil
from collections import defaultdict

# Directories and files used throughout the script
BASE_DIR = "kubernetes/apps"
DEPENDENCIES_DIR = "dependencies"
OUTPUT_FILE = f"{DEPENDENCIES_DIR}/DEPENDENCIES-full.md"
SUMMARY_FILE = f"{DEPENDENCIES_DIR}/DEPENDENCIES-SUMMARY.md"

# Environment variables for headless Chrome used by mermaid CLI
env = os.environ.copy()
env["PUPPETEER_EXECUTABLE_PATH"] = os.path.expanduser(
    "~/.cache/puppeteer/chrome/linux-131.0.6778.204/chrome-linux64/chrome"
)
env["CHROME_DEVEL_SANDBOX"] = "/opt/google/chrome/chrome-sandbox"

# Core data structures
graph = defaultdict(set)
nodes = set()

external_secret_apps = {}
sops_apps = set()
warnings = []
ks_path_map = {}  # path -> (name, namespace, dependsOn)
hr_path_map = {}  # path -> (name, namespace, dependsOn)
empty_namespaces = []


def safe_load(path):
    """Safely load YAML documents from a file."""
    try:
        with open(path) as f:
            return list(yaml.safe_load_all(f))
    except Exception:
        return []


def infer_app_id_from_path(path):
    """Infer app ID from a file path by isolating the relative path under 'apps'."""
    parts = path.replace("\\", "/").split("/")
    if "apps" not in parts:
        return None
    idx = parts.index("apps")
    rel_parts = parts[idx + 1 :]
    return "/".join(rel_parts[:]) if rel_parts else None


def parse_file(path):
    """Parse a YAML file looking for Kustomization or HelmRelease definitions and build the graph."""
    docs = safe_load(path)
    for doc in docs:
        if not isinstance(doc, dict):
            continue

        kind = doc.get("kind")
        metadata = doc.get("metadata", {})
        name = metadata.get("name")
        namespace = metadata.get("namespace")

        if kind not in ["Kustomization", "HelmRelease"] or not name:
            continue

        if kind == "Kustomization" and "ks.yaml" not in path:
            continue

        if kind == "HelmRelease":
            depends = doc.get("spec", {}).get("dependsOn", [])
            if not depends:
                continue

        if not namespace:
            rel_path = os.path.relpath(os.path.dirname(path), BASE_DIR)
            rel_path_norm = os.path.normpath(rel_path)

            matched_namespace = None
            for ks_path, (_, ks_ns, _) in ks_path_map.items():
                if rel_path_norm in ks_path:
                    matched_namespace = ks_ns
                    break

            for hr_path, (_, hr_ns, _) in hr_path_map.items():
                if rel_path_norm in hr_path:
                    matched_namespace = hr_ns
                    break

            namespace = matched_namespace or "default"

        full_id = f"{namespace}/{name}"
        nodes.add(full_id)

        # Add graph edges based on dependsOn
        for dep in doc.get("spec", {}).get("dependsOn", []):
            dep_ns = dep.get("namespace", "default")
            dep_name = dep.get("name")
            if dep_name:
                dep_id = f"{dep_ns}/{dep_name}"
                graph[dep_id].add(full_id)


def detect_secret_files():
    """Identify which apps are using sops or external secrets."""
    for root, _, files in os.walk(BASE_DIR):
        if ".private" in root.split(os.sep):
            continue
        app_id = infer_app_id_from_path(root)
        if not app_id:
            continue

        if "secret.sops.yaml" in files:
            sops_apps.add(app_id)
            graph["secret-sops"].add(app_id)
            nodes.add("secret-sops")

        if "externalsecret.yaml" in files:
            ext_path = os.path.join(root, "externalsecret.yaml")
            external_secret_apps[app_id] = ext_path
            graph["external-secrets"].add(app_id)
            nodes.add("external-secrets")


def collect_ks_blocks():
    """Populate ks_path_map from ks.yaml and hr_path_map from helmrelease.yaml files (only if dependsOn exists)."""
    for root, _, files in os.walk(BASE_DIR):
        if ".private" in root.split(os.sep):
            continue

        for f in files:
            full_file_path = os.path.join(root, f)
            if f not in ["ks.yaml", "helmrelease.yaml"]:
                continue

            try:
                with open(full_file_path) as fobj:
                    docs = list(yaml.safe_load_all(fobj))
                    for doc in docs:
                        if not isinstance(doc, dict):
                            continue

                        path = doc.get("spec", {}).get("path", "")
                        name = doc.get("metadata", {}).get("name")
                        namespace = doc.get("metadata", {}).get("namespace")

                        if not namespace:
                            inferred = infer_app_id_from_path(full_file_path)
                            namespace = (
                                inferred.split("/")[0]
                                if inferred and "/" in inferred
                                else "default"
                            )

                        if f == "ks.yaml" and (not name or not path):
                            continue

                        if path:
                            full_path = os.path.normpath(path)
                        else:
                            full_path = os.path.relpath(root, BASE_DIR)

                        depends = doc.get("spec", {}).get("dependsOn", [])

                        if f == "ks.yaml" and depends:
                            ks_path_map[full_path] = (name, namespace, depends)
                        elif f == "helmrelease.yaml" and depends:
                            hr_path_map[full_path] = (name, namespace, depends)

            except Exception as e:
                warnings.append(f"⚠️ Failed to parse {f} at {full_file_path}: {e}")


def check_ks_includes():
    """Verify that externalsecret.yaml files are included in appropriate ks.yaml files."""
    for app_id, ext_path in external_secret_apps.items():
        ext_folder = os.path.normpath(os.path.dirname(ext_path))

        included = False
        has_dep_block = False

        for ks_path, (name, namespace, depends) in ks_path_map.items():
            if ext_folder == ks_path:
                included = True
                for dep in depends:
                    if (
                        dep.get("name") == "external-secrets-stores"
                        and dep.get("namespace") == "external-secrets"
                    ):
                        has_dep_block = True

        if not included:
            warnings.append(
                f"{app_id} externalsecret.yaml NOT included in any ks.yaml (path mismatch)"
            )
        elif not has_dep_block:
            warnings.append(
                f"{app_id} externalsecret.yaml missing dependsOn: external-secrets-stores"
            )


def find_cycles(graph):
    """Detect circular dependencies in the graph."""
    visited = set()
    rec_stack = set()
    cycles = []

    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])

        path.pop()
        rec_stack.remove(node)

    for node in graph:
        if node not in visited:
            dfs(node, [])

    return cycles


def write_mermaid(graph):
    """Write the full dependency graph to a Mermaid file."""
    with open(OUTPUT_FILE, "w") as f:
        f.write("```mermaid\n")
        f.write("---\nconfig:\n  layout: elk\n---\n")
        f.write("flowchart LR\n\n")
        for src in sorted(graph.keys()):
            for dst in sorted(graph[src]):
                f.write(f"  {src} --> {dst}\n")
        f.write("```\n")


def check_string_in_tuples(list_of_tuples, target_string):
    for tuple_item in list_of_tuples:
        if target_string in tuple_item:
            return True
    return False


def write_namespace_files(graph):
    """Write namespace-specific dependency graphs with intra-namespace edges grouped in a subgraph."""
    namespace_nodes = defaultdict(set)

    # Track which nodes belong to which namespace
    for node in nodes:
        if "/" in node:
            ns, _ = node.split("/", 1)
            namespace_nodes[ns].add(node)

    for ns in sorted(namespace_nodes.keys()):

        if ns in ["external-secrets", "secret-sops"]:
            print(f"📭 Skipping namespace '{ns}' as it is a special namespace.")
            continue

        ns_nodes = namespace_nodes[ns]
        intra_edges = []
        cross_edges = []
        inside_ns = []

        for src in graph:
            for dst in graph[src]:
                if (src in ns_nodes and dst in ns_nodes) or (ns in src and ns in dst):
                    intra_edges.append((src, dst))
                elif src in ns_nodes or dst in ns_nodes:
                    cross_edges.append((src, dst))
                if ns in src and "app" not in src and src not in inside_ns:
                    inside_ns.append(src)
                if ns in dst and "app" not in dst and dst not in inside_ns:
                    inside_ns.append(dst)
        for item in inside_ns:
            if check_string_in_tuples(intra_edges, item) and check_string_in_tuples(cross_edges, item):
                inside_ns.remove(item)
        if not intra_edges and not cross_edges:
            print(f"📭 No dependencies found in namespace '{ns}', skipping file creation.")
            empty_namespaces.append(ns)
            continue

        filename = f"{DEPENDENCIES_DIR}/DEPENDENCIES-{ns}.md"
        with open(filename, "w") as f:
            f.write("```mermaid\n")
            f.write("---\nconfig:\n  layout: elk\n---\n")
            f.write("flowchart LR\n\n")

            # Intra-namespace edges grouped in a subgraph
            if intra_edges or inside_ns:

                # print(f"inside_ns: {inside_ns}")
                f.write(f'  subgraph "ns: {ns}"\n')
                for item in sorted(inside_ns):
                    f.write(f'    {item}\n')
                if intra_edges:
                  for src, dst in sorted(intra_edges):
                      f.write(f'    {src} --> {dst}\n')
                f.write("  end\n")

            # Cross-namespace edges outside subgraph
            for src, dst in sorted(cross_edges):
                f.write(f"  {src} --> {dst}\n")

            f.write("```\n")


def render_mermaid_pngs():
    """Render all generated Mermaid markdown files into PNG images using Mermaid CLI."""
    full_deps_dir = os.path.abspath(DEPENDENCIES_DIR)

    for filename in os.listdir(full_deps_dir):
        if not filename.startswith("DEPENDENCIES") or not filename.endswith(".md"):
            continue
        if "SUMMARY" in filename:
            continue  # Skip summary file

        md_path = os.path.join(full_deps_dir, filename)
        png_path = md_path.replace(".md", ".png")

        cmd = ["pnpm", "mmdc", "--input", md_path, "-o", png_path, "-t", "neutral"]
        try:
            if os.path.exists(png_path):
                os.remove(png_path)
            subprocess.run(cmd, check=True, env=env)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to render {png_path}: {e}")


def fix_png_suffix_issue():
    """Fix files rendered with unexpected '-1.png' suffixes from Mermaid CLI."""
    print("🔧 Fixing -1.png suffix issue...")
    for filename in os.listdir(DEPENDENCIES_DIR):
        if filename.endswith("-1.png"):
            original = filename.replace("-1.png", ".png")
            original_path = os.path.join(DEPENDENCIES_DIR, original)
            current_path = os.path.join(DEPENDENCIES_DIR, filename)

            if not os.path.exists(original_path):
                shutil.move(current_path, original_path)
            else:
                print(
                    f"⚠️ Cannot rename {filename} to {original}, target already exists."
                )


def write_summary():
    """Write the summary of SOPS and ExternalSecrets usage, circular dependencies, and skipped namespaces."""
    with open(SUMMARY_FILE, "w") as f:
        f.write("SOPS Secrets:\n")
        for app in sorted(sops_apps):
            f.write(f"  - {app}\n")

        f.write("\nExternal Secrets:\n")
        for app in sorted(external_secret_apps):
            f.write(f"  - {app}\n")

        f.write("\nUsing Both:\n")
        for app in sorted(sops_apps & external_secret_apps.keys()):
            f.write(f"  - {app}\n")

        cycles = find_cycles(graph)
        if cycles:
            f.write("\nCircular Dependencies:\n")
            for cycle in cycles:
                f.write("    " + "\n    → ".join(cycle) + "\n")

        if empty_namespaces:
            f.write("\nNamespaces with no dependencies (no file created):\n")
            for ns in sorted(empty_namespaces):
                f.write(f"  - {ns}\n")

        if hr_path_map:
            f.write("\nHelmRelease dependsOn blocks:\n")
            for path, (name, ns, depends) in sorted(hr_path_map.items()):
                f.write(f"  - {ns}/{name}:\n")
                for dep in depends:
                    dep_ns = dep.get("namespace", "default")
                    dep_name = dep.get("name")
                    if dep_name:
                        f.write(f"      → {dep_ns}/{dep_name}\n")


def write_readme():
    """Write a README.md file summarizing all generated graph images and the summary report."""
    readme_path = os.path.join(DEPENDENCIES_DIR, "README.md")
    print(f"📝 Writing README to {readme_path}...")

    with open(readme_path, "w") as f:
        f.write("# 📊 Kubernetes App Dependencies\n\n")
        f.write("Automatically generated dependency graphs for each namespace.\n\n")

        full_img = "DEPENDENCIES-full.png"
        if full_img in os.listdir(DEPENDENCIES_DIR):
            f.write("## 🔗 Full Dependency Graph\n\n")
            f.write(f"![Full](./{full_img})\n\n")

        f.write("## 📂 Namespace Dependency Graphs\n\n")
        for filename in sorted(os.listdir(DEPENDENCIES_DIR)):
            if filename.startswith("DEPENDENCIES-") and filename.endswith(".png"):
                if filename in [full_img, "DEPENDENCIES-SUMMARY.png"]:
                    continue
                title = filename.replace("DEPENDENCIES-", "").replace(".png", "")
                f.write(f"### {title}\n\n")
                f.write(f"![{title}](./{filename})\n\n")

        summary_path = os.path.join(DEPENDENCIES_DIR, "DEPENDENCIES-SUMMARY.md")
        if os.path.exists(summary_path):
            f.write("## 📋 Summary\n\n")
            with open(summary_path, "r") as summary_file:
                summary_content = summary_file.read()
                f.write("```\n")
                f.write(summary_content)
                f.write("```\n")


if __name__ == "__main__":
    os.makedirs(DEPENDENCIES_DIR, exist_ok=True)

    print("🔍 Scanning for Kubernetes resources...")

    collect_ks_blocks()

    for root, _, files in os.walk(BASE_DIR):
        if ".private" in root.split(os.sep):
            continue
        for f in files:
            if f.endswith((".yaml", ".yml")):
                parse_file(os.path.join(root, f))

    detect_secret_files()
    check_ks_includes()
    write_mermaid(graph)
    write_namespace_files(graph)
    write_summary()
    write_readme()

    # print(f"nodes: {nodes}")
    # print(f"graph: {graph}")

    cycles = find_cycles(graph)
    if cycles:
        print("\n🔁 \033[4mCircular dependencies detected\033[0m:")
        for cycle in cycles:
            print("    " + "\n    → ".join(cycle))

    if warnings:
        print("\n⚠️  \033[4mExternalSecret inclusion warnings\033[0m:")
        for warn in sorted(warnings):
            print(f"    {warn}")
    else:
        print("\n✅ All externalsecret.yaml files are correctly included in ks.yaml.")

    print("\n🖼️ Rendering Mermaid PNGs for all namespaces...")
    render_mermaid_pngs()
    fix_png_suffix_issue()

    print("\n🔐 Apps using \033[1msecret.sops.yaml\033[0m:")
    for app in sorted(sops_apps):
        print(f"    {app}")

    print("\n🔑 Apps using \033[1mexternalsecret.yaml\033[0m:")
    for app in sorted(external_secret_apps):
        print(f"    {app}")

    print("\n📦 Apps using \033[1mboth\033[0m:")
    for app in sorted(sops_apps & external_secret_apps.keys()):
        print(f"    {app}")

    if hr_path_map:
        print("\n🧩 HelmReleases with dependsOn blocks:")
        for path, (name, ns, depends) in sorted(hr_path_map.items()):
            print(f"  - {ns}/{name}:")
            for dep in depends:
                dep_ns = dep.get("namespace", "default")
                dep_name = dep.get("name")
                if dep_name:
                    print(f"      → {dep_ns}/{dep_name}")

    print(f"\n✅ Dependency graph written to {OUTPUT_FILE}")
    print(f"✅ Summary written to {SUMMARY_FILE}")
