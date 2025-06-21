#!/usr/bin/env python3
import os
import sys
import requests
import argparse
from pathlib import Path
import yaml
import json
import re
from collections import defaultdict
import requests

RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"


ROOT_DIR = Path(__file__).resolve().parent.parent / "kubernetes"
TALENV_FILE = Path(__file__).resolve().parent.parent / "talos" / "talenv.yaml"

# Load Talenv metadata
with TALENV_FILE.open() as f:
    talenv = yaml.safe_load(f)

k8s_version = talenv.get("kubernetesVersion", "v1.32.3")
talos_version = talenv.get("talosVersion", "v1.10.3")

# Define base schema source preference
YANNH_SCHEMA = f"https://raw.githubusercontent.com/yannh/kubernetes-json-schema/refs/heads/master/{k8s_version}"
FLUXCD_COMMUNITY_BASE = "https://raw.githubusercontent.com/fluxcd-community/flux2-schemas/main"
KUBERNETES_SCHEMAS = "https://kubernetes-schemas.pages.dev"
MOVISHELL_CRD = "https://crd.movishell.pl"
DATREEIO_CRD = "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main"

# Common kind-to-schema mappings for Kubernetes core and common CRDs
CORE_KIND_MAP = {
    "Pod": "pod.json",
    "Job": "job.json",
    "CronJob": "cronjob.json",
    "Service": "service.json",
    "Ingress": "ingress.json",
    "ConfigMap": "configmap.json",
    "Secret": "secret.json",
    "PersistentVolumeClaim": "persistentvolumeclaim.json",
    "Deployment": "deployment.json",
    "StatefulSet": "statefulset.json",
    "DaemonSet": "daemonset.json",
    "ServiceAccount": "serviceaccount.json",
    "Endpoints": "endpoints.json",
    "EndpointSlice": "endpointslice.json",
    "Namespace": "namespace.json",
    "ClusterRole": "clusterrole.json",
    "ClusterRoleBinding": "clusterrolebinding.json",
    "Role": "role.json",
    "RoleBinding": "rolebinding.json",
    "CustomResourceDefinition": "customresourcedefinition.json",
    "ValidatingWebhookConfiguration": "validatingwebhookconfiguration.json",
    "HorizontalPodAutoscaler": "horizontalpodautoscaler.json",
    "StorageClass": "storageclass.json",
}

# Include flux, volsync, and other ecosystem extensions
EXTENSIONS = {
    "HelmRelease":                    f"{FLUXCD_COMMUNITY_BASE}/helmrelease-helm-v2.json",
    "HelmRepository":                 f"{FLUXCD_COMMUNITY_BASE}/helmrepository-source-v1.json",
    "ImageUpdateAutomation":          f"{FLUXCD_COMMUNITY_BASE}/imageupdateautomation-image-v1beta1.json",
    "OCIRepository":                  f"{FLUXCD_COMMUNITY_BASE}/ocirepository-source-v1.json",
    "AlertmanagerConfig":             f"{KUBERNETES_SCHEMAS}/monitoring.coreos.com/alertmanagerconfig_v1alpha1.json",
    "ClusterSecretStore":             f"{KUBERNETES_SCHEMAS}/external-secrets.io/clustersecretstore_v1beta1.json",
    "ExternalSecret":                 f"{KUBERNETES_SCHEMAS}/external-secrets.io/externalsecret_v1beta1.json",
    "GitRepository":                  f"{KUBERNETES_SCHEMAS}/source.toolkit.fluxcd.io/gitrepository_v1.json",
    "Kustomization":                  f"{KUBERNETES_SCHEMAS}/kustomize.toolkit.fluxcd.io/kustomization_v1.json",
    "PrometheusRule":                 f"{KUBERNETES_SCHEMAS}/monitoring.coreos.com/prometheusrule_v1.json",
    "ReplicationDestination":         f"{KUBERNETES_SCHEMAS}/volsync.backube/replicationdestination_v1alpha1.json",
    "ReplicationSource":              f"{KUBERNETES_SCHEMAS}/volsync.backube/replicationsource_v1alpha1.json",
    "ServiceMonitor":                 f"{KUBERNETES_SCHEMAS}/monitoring.coreos.com/servicemonitor_v1.json",
    "VolumeSnapshotClass":            f"{KUBERNETES_SCHEMAS}/snapshot.storage.k8s.io/volumesnapshotclass_v1.json",
    "Cluster":                        f"{MOVISHELL_CRD}/postgresql.cnpg.io/cluster_v1.json",
    "ClusterPolicy":                  f"{MOVISHELL_CRD}/kyverno.io/clusterpolicy_v1.json",
    "PodMonitor":                     f"{MOVISHELL_CRD}/monitoring.coreos.com/podmonitor_v1.json",
    "ScheduledBackup":                f"{MOVISHELL_CRD}/postgresql.cnpg.io/scheduledbackup_v1.json",
    "ScrapeConfig":                   f"{MOVISHELL_CRD}/monitoring.coreos.com/scrapeconfig_v1alpha1.json",
    "Certificate":                    f"{DATREEIO_CRD}/cert-manager.io/certificate_v1.json",
    "CiliumL2AnnouncementPolicy":     f"{DATREEIO_CRD}/cilium.io/ciliuml2announcementpolicy_v2alpha1.json",
    "CiliumLoadBalancerIPPool":       f"{DATREEIO_CRD}/cilium.io/ciliumloadbalancerippool_v2alpha1.json",
    "CiliumNetworkPolicy":            f"{DATREEIO_CRD}/cilium.io/ciliumnetworkpolicy_v2.json",
    "ClusterIssuer":                  f"{DATREEIO_CRD}/cert-manager.io/clusterissuer_v1.json",
    "DNSEndpoint":                    f"{DATREEIO_CRD}/externaldns.k8s.io/dnsendpoint_v1alpha1.json",
    "MutatingAdmissionPolicy":        f"{YANNH_SCHEMA}/mutatingadmissionpolicy-admissionregistration-v1alpha1.json",
    "MutatingAdmissionPolicyBinding": f"{YANNH_SCHEMA}/mutatingadmissionpolicybinding-admissionregistration-v1alpha1.json",
    "Dragonfly":                      "https://lds-schemas.pages.dev/dragonflydb.io/dragonfly_v1alpha1.json",
}

CUSTOM_SCHEMAS = {
    "MariaDB": "https://raw.githubusercontent.com/mariadb-operator/mariadb-operator/main/config/crd/bases/k8s.mariadb.com_mariadbs.yaml"
    # "K8sGPT": "https://raw.githubusercontent.com/k8sgpt-ai/k8sgpt/main/config/crd/bases/k8sgpt.ai_k8sgpts.yaml",
    # "DiskPool": "https://raw.githubusercontent.com/zotregistry/zot/main/config/crd/bases/zotregistry.io_diskpools.yaml",
}

KIND_TO_SCHEMA = {k: f"{YANNH_SCHEMA}/{v}" for k, v in CORE_KIND_MAP.items()}
KIND_TO_SCHEMA.update({k: v for k, v in EXTENSIONS.items() if v})


def download_custom_schema(kind: str, url: str):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            raw_path = Path("schemas/raw") / f"{kind.lower()}.yaml"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_path, "w") as f:
                f.write(response.text)
            print(f"{CYAN}\u2139\ufe0f  Downloaded raw CRD for {kind} to {raw_path}{RESET}")

            final_path = Path("schemas") / f"{kind.lower()}.json"
            extract_openapi_schema(raw_path, final_path)
        else:
            print(f"{RED}\u274c {kind}: {url} (status code: {response.status_code}){RESET}")
    except requests.RequestException as e:
        print(f"{RED}\u274c {kind}: {url} (error: {e}){RESET}")


def extract_openapi_schema(crd_yaml_path: Path, output_path: Path):
    with open(crd_yaml_path, "r") as f:
        crd = yaml.safe_load(f)
    versions = crd.get("spec", {}).get("versions", [])
    for version in versions:
        if "schema" in version and "openAPIV3Schema" in version["schema"]:
            schema = version["schema"]["openAPIV3Schema"]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as out:
                json.dump(schema, out, indent=2)
            print(f"{GREEN}\u2705 Extracted schema to {output_path}{RESET}")
            return
    print(f"{RED}\u274c Failed to find openAPIV3Schema in {crd_yaml_path}{RESET}")


def test_schema():
    print(f"{YELLOW}Testing schemas...{RESET}")
    merged_schemas = {**KIND_TO_SCHEMA, **CUSTOM_SCHEMAS}
    for kind, schema in merged_schemas.items():
        try:
            response = requests.head(schema)
            if response.status_code == 200:
                print(f"{GREEN}\u2705 {kind}: {schema}{RESET}")
            else:
                print(f"{RED}\u274c {kind}: {schema} (status code: {response.status_code}){RESET}")
        except requests.RequestException as e:
            print(f"{RED}\u274c {kind}: {schema} (error: {e}){RESET}")


def get_schema_url(kind, doc_buffer, yaml_file_short, doc_index, args):
    if kind == "HelmRelease":
        try:
            parsed = yaml.safe_load("".join(doc_buffer))
            chart_spec = parsed.get("spec", {}).get("chart", {}).get("spec", {})
            chart_ref = parsed.get("spec", {}).get("chartRef", {}).get("name", "")
            if chart_spec.get("chart") == "app-template" or chart_ref == "app-template":
                return "https://raw.githubusercontent.com/bjw-s-labs/helm-charts/refs/tags/app-template-3.7.3/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json"
            return EXTENSIONS.get("HelmRelease")
        except Exception as e:
            print(f"{RED}\u26a0\ufe0f  Failed to inspect HelmRelease chart in {yaml_file_short}: {e}{RESET}")
            return EXTENSIONS.get("HelmRelease")
    elif kind in CUSTOM_SCHEMAS:
        local_path = Path("schemas") / f"{kind.lower()}.json"
        if local_path.exists():
            return os.path.relpath(local_path, start=ROOT_DIR).replace(os.sep, "/")
        else:
            print(f"{RED}\u274c {kind}: schema file not found at {local_path}{RESET}")
            return CUSTOM_SCHEMAS[kind]  # fallback
    elif kind == "Kustomization" and "ks.yaml" in yaml_file_short:
        return f"{FLUXCD_COMMUNITY_BASE}/kustomization-kustomize-v1.json"
    return KIND_TO_SCHEMA.get(kind)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--do-it", action="store_true")
    parser.add_argument("--detail", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--hr", action="store_true")
    parser.add_argument("--test-schema", action="store_true")
    parser.add_argument("--dl-schema", action="store_true")
    args = parser.parse_args()

    if args.test_schema:
        test_schema()
        return
    if args.dl_schema:
        print(f"{YELLOW}Downloading custom schemas...{RESET}")
        for kind, url in CUSTOM_SCHEMAS.items():
            download_custom_schema(kind, url)
        return

    for yaml_file in ROOT_DIR.rglob("*.yaml"):
        if any(part in yaml_file.parts for part in [".private", ".venv", "docker"]):
            continue
        if args.hr and "helmrelease" not in yaml_file.name:
            continue
        yaml_file_short = "kubernetes/" + str(yaml_file.relative_to(ROOT_DIR))
        with open(yaml_file, "r") as f:
            lines = f.readlines()

        changed = False
        output_lines = []
        doc_buffer = []
        doc_index = 0

        for line in lines + ["---"]:
            if line.strip() == "---":
                if doc_buffer:
                    kind, schema_url = None, None
                    existing_schema_idx = None
                    existing_schema_line = None

                    for i, l in enumerate(doc_buffer):
                        if l.strip().startswith("# yaml-language-server: $schema="):
                            existing_schema_idx = i
                            existing_schema_line = l.strip()
                        elif l.startswith("kind:"):
                            kind = l.strip().split(":", 1)[1].strip()

                    schema_url = get_schema_url(kind, doc_buffer, yaml_file_short, doc_index, args)
                    if not kind or not schema_url:
                        print(f"{YELLOW}\u26a0\ufe0f  Unknown or unsupported kind in {yaml_file_short} [doc {doc_index}]: {kind or 'None'}{RESET}")
                        if not args.do_it and (args.detail or args.full):
                            print("")
                        output_lines.extend(doc_buffer + [""])
                        doc_buffer = []
                        doc_index += 1
                        continue

                    new_schema_line = f"---\n# yaml-language-server: $schema={schema_url}"

                    if existing_schema_idx is not None:
                        if doc_buffer[existing_schema_idx].strip() != new_schema_line.replace("---\n",""):
                            doc_buffer[existing_schema_idx] = new_schema_line + "\n"
                            changed = True
                            if not args.do_it and (args.detail or args.full):
                                print(f"{YELLOW}[DRY-RUN]{RESET} {RED}{yaml_file_short} [doc {doc_index}] - CHANGE needed{RESET}\n    FROM: {existing_schema_line.replace('# yaml-language-server: ', '')}\n    TO:   {new_schema_line.replace('---\n# yaml-language-server: ', '')}\n")
                        elif not args.do_it and args.full:
                            print(f"{YELLOW}[DRY-RUN]{RESET} {GREEN}{yaml_file_short} [doc {doc_index}] - no change needed{RESET}\n    \u2705 OK: {existing_schema_line.replace('---\n# yaml-language-server: ', '')}\n")
                    else:
                        if not args.do_it and (args.detail or args.full):
                            print(f"{YELLOW}[DRY-RUN]{RESET} {RED}{yaml_file_short} [doc {doc_index}] - CHANGE needed{RESET}\n    FROM: {RED}<none>{RESET}\n    TO:   {new_schema_line.replace('---\n# yaml-language-server: ', '')}\n")
                        doc_buffer.insert(0, new_schema_line + "\n")
                        changed = True

                    output_lines.extend(doc_buffer + [""])
                    # output_lines.extend(doc_buffer + ["---\n"])
                    doc_buffer = []
                    doc_index += 1
                # else:
                #     output_lines.append("---\n")
            else:
                doc_buffer.append(line)

        if changed:
            if args.do_it:
                with open(yaml_file, "w") as f:
                    f.writelines(output_lines)
                print(f"{GREEN}\u2705 Updated:{RESET} {yaml_file_short}")
            elif not args.detail and not args.full:
                print(f"{YELLOW}[DRY-RUN]{RESET} Would update: {yaml_file_short}")

if __name__ == "__main__":
    main()
