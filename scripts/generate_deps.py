#!/usr/bin/env python3
import yaml, os
from collections import defaultdict
# from graphviz import Digraph

BASE_DIR = "kubernetes/apps"
OUTPUT_FILE = "DEPENDENCIES.md"
SUMMARY_FILE = "DEPENDENCIES-SUMMARY.md"

graph = defaultdict(set)
nodes = set()

external_secret_apps = {}
sops_apps = set()
warnings = []
ks_path_map = {}  # path -> (name, namespace, dependsOn)


def safe_load(path):
    try:
        with open(path) as f:
            return list(yaml.safe_load_all(f))
    except Exception:
        return []


def infer_app_id_from_path(path):
    parts = path.replace("\\", "/").split("/")
    if "apps" not in parts:
        return None
    idx = parts.index("apps")
    rel_parts = parts[idx + 1:]  # everything after "apps"
    return "/".join(rel_parts[:]) if rel_parts else None


def parse_file(path):
    docs = safe_load(path)
    for doc in docs:
        if not isinstance(doc, dict):
            continue

        kind = doc.get("kind")
        metadata = doc.get("metadata", {})
        name = metadata.get("name")
        namespace = metadata.get("namespace", "default")
        if not name:
            continue

        full_id = f"{namespace}/{name}"
        nodes.add(full_id)

        if kind in ["HelmRelease", "Kustomization"]:
            for dep in doc.get("spec", {}).get("dependsOn", []):
                dep_ns = dep.get("namespace", "default")
                dep_name = dep.get("name")
                if dep_name:
                    dep_id = f"{dep_ns}/{dep_name}"
                    graph[dep_id].add(full_id)


def detect_secret_files():
    print("\n🔍 Detecting secret files...")
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
    print("🔍 Getting Kustomization dependsOn blocks...")
    for root, _, files in os.walk(BASE_DIR):
        if ".private" in root.split(os.sep):
            continue
        for f in files:
            if f == "ks.yaml":
                ks_path = os.path.join(root, f)
                try:
                    with open(ks_path) as fobj:
                        docs = list(yaml.safe_load_all(fobj))
                        for doc in docs:
                            if isinstance(doc, dict):
                                path = doc.get("spec", {}).get("path", "")
                                name = doc.get("metadata", {}).get("name")
                                namespace = doc.get("metadata", {}).get("namespace", "default")
                                if not name or not path:
                                    continue
                                full_path = os.path.normpath(path)
                                depends = doc.get("spec", {}).get("dependsOn", [])
                                ks_path_map[full_path] = (name, namespace, depends)
                except Exception as e:
                    warnings.append(f"⚠️ Failed to parse ks.yaml at {ks_path}: {e}")


def check_ks_includes():
    print("🔍 Checking external-secrets-stores inclusion in ks.yaml...")
    for app_id, ext_path in external_secret_apps.items():
        ext_folder = os.path.normpath(os.path.dirname(ext_path))

        included = False
        has_dep_block = False

        for ks_path, (name, namespace, depends) in ks_path_map.items():
            if ext_folder == ks_path:
                included = True
                for dep in depends:
                    if dep.get("name") == "external-secrets-stores" and dep.get("namespace") == "external-secrets":
                        has_dep_block = True

        if not included:
            warnings.append(f"{app_id} externalsecret.yaml NOT included in any ks.yaml (path mismatch)")
        elif not has_dep_block:
            warnings.append(f"{app_id} externalsecret.yaml missing dependsOn: external-secrets-stores")


def find_cycles(graph):
    print("🔍 Detecting circular dependencies...")
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
    with open(OUTPUT_FILE, "w") as f:
        f.write("---\nconfig:\n  layout: elk\n---\n")
        f.write("flowchart LR\n\n")
        for src in sorted(graph.keys()):
            for dst in sorted(graph[src]):
                f.write(f"  {src} --> {dst}\n")


def write_summary():
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


# def render_graphviz_png(graph, ns_filter):
#     ns_graph = Digraph(format="png")
#     ns_graph.attr(rankdir="LR")

#     for src in sorted(graph.keys()):
#         if not src.startswith(ns_filter + "/"):
#             continue
#         for dst in sorted(graph[src]):
#             ns_graph.edge(src, dst)

#     filename = f"DEPENDENCIES-{ns_filter}"
#     ns_graph.render(filename=filename, cleanup=True)
#     print(f"🖼️  PNG written to {filename}.png")


if __name__ == "__main__":
    print("🔍 Scanning for Kubernetes resources...")
    for root, _, files in os.walk(BASE_DIR):
        if ".private" in root.split(os.sep):
            continue
        for f in files:
            if f.endswith((".yaml", ".yml")):
                parse_file(os.path.join(root, f))

    detect_secret_files()
    collect_ks_blocks()
    check_ks_includes()
    write_mermaid(graph)
    write_summary()

    # # Render PNGs for each namespace
    # all_namespaces = {app_id.split("/")[0] for app_id in nodes if "/" in app_id}
    # for ns in sorted(all_namespaces):
    #     render_graphviz_png(graph, ns)

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

    print("\n🔐 Apps using \033[1msecret.sops.yaml\033[0m:")
    for app in sorted(sops_apps):
        print(f"    {app}")

    print("\n🔑 Apps using \033[1mexternalsecret.yaml\033[0m:")
    for app in sorted(external_secret_apps):
        print(f"    {app}")

    print("\n📦 Apps using \033[1mboth\033[0m:")
    for app in sorted(sops_apps & external_secret_apps.keys()):
        print(f"    {app}")

    print(f"\n✅ Dependency graph written to {OUTPUT_FILE}")
    print(f"✅ Summary written to {SUMMARY_FILE}")

