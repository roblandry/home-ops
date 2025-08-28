# Home-ops Kubernetes Cluster

This repository contains a complete home Kubernetes cluster setup using Talos Linux, Flux GitOps, and various applications. The cluster uses Kubernetes for orchestration, Helm for application management, SOPS for secret encryption, and Cloudflare for external access.

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

### Bootstrap and Setup
- **Development Environment Setup:**
  - Install mise tool manager: `curl https://mise.run | sh` (installs to `~/.local/bin/mise`)
  - If mise installation fails, install tools manually via system packages
  - `mise trust` - trust the .mise.toml configuration
  - `pip install pipx` - install pipx for Python tool management
  - `mise install` - installs all required CLI tools (takes 5-10 minutes). NEVER CANCEL. Set timeout to 15+ minutes.
- **Alternative installation if mise fails:**
  - `wget -O- "https://github.com/go-task/task/releases/latest/download/task_linux_amd64.tar.gz" | tar -xz -C /tmp && sudo mv /tmp/task /usr/local/bin/`
  - `pipx install makejinja==2.8.1`
  - Install kubectl, flux, helm, yq, sops via system package manager or direct downloads

- **Required Python Tools:**
  - `pipx install makejinja==2.8.1` - template engine for configuration generation
  - `pip install -r requirements.txt` - Python dependencies for scripts

- **Core CLI Tools:**
  - Task runner: Download from `https://github.com/go-task/task/releases/latest/download/task_linux_amd64.tar.gz`
  - kubectl: Already available in most CI environments
  - Other tools: flux2, helm, talosctl, yq, sops (installed via mise or manually)

### Key Commands
- **List available tasks:** `task --list`
- **Validate schemas:** `python3 scripts/check-schemas.py` (takes ~1 second)
- **Generate dependency graphs:** `python3 scripts/generate_deps.py` (takes ~2 seconds, may fail on PNG generation if pnpm/mermaid unavailable)
- **Fix schemas:** `python3 scripts/fix-schemas.py --test-schema` (may fail with API rate limits - ignore 403 errors)
- **Reconcile Flux:** `task reconcile` (requires active Kubernetes cluster)

### Build and Test Timing
- **mise install:** 5-10 minutes. NEVER CANCEL. Set timeout to 15+ minutes.
- **Schema validation:** ~1 second (scripts/check-schemas.py)
- **Dependency generation:** ~2 seconds (scripts/generate_deps.py)
- **YAML syntax validation:** <1 second for individual files
- **CI workflows:** 2-5 minutes for flux-local tests
- **Cluster bootstrap (task bootstrap:talos):** 10+ minutes. NEVER CANCEL. Set timeout to 30+ minutes.
- **App bootstrap (task bootstrap:apps):** 10+ minutes. NEVER CANCEL. Set timeout to 30+ minutes.

## Validation

### Schema and Manifest Validation
- **ALWAYS validate schemas:** Run `python3 scripts/check-schemas.py` before committing changes
- **Check dependencies:** Run `python3 scripts/generate_deps.py` to validate dependency graphs and check for circular dependencies
- **Kubernetes manifests:** CI uses flux-local for manifest validation via GitHub Actions
- **Schema fixing:** Run `python3 scripts/fix-schemas.py --do-it` to update schemas (requires GitHub token for some operations)

### Manual Testing Scenarios
- **Validate YAML syntax:** Check that all .yaml files in kubernetes/ directory are valid
  - Test: `find kubernetes/ -name "*.yaml" | head -5 | xargs -I {} python3 -c "import yaml; yaml.safe_load(open('{}')); print('Valid: {}')"`
- **Check External Secrets:** Ensure externalsecret.yaml files are properly referenced in ks.yaml files
  - Dependency script will show warnings for missing references
- **Dependency validation:** Look for circular dependencies in the generated dependency graphs
  - Output will show "🔁 Circular dependencies detected" if any exist
- **Schema compliance:** Verify all Kubernetes resources have proper schema annotations
  - Use `python3 scripts/check-schemas.py` to see schema coverage
- **Task command verification:** Ensure task commands fail gracefully when cluster is unavailable
  - Test: `task reconcile` should show "precondition not met" error

### CI/CD Validation
- **GitHub Actions:** `.github/workflows/flux-local.yaml` runs on every PR to validate Kubernetes manifests
- **Flux validation:** Tests HelmRelease and Kustomization resources using flux-local
- **Labels:** Auto-labeling via `.github/workflows/labeler.yaml`
- **Tool updates:** Weekly mise tool updates via `.github/workflows/mise.yaml`

## Bootstrap Commands (Cluster Required)

**WARNING: These commands require an actual Talos cluster and will fail in CI/development environments:**

- **Bootstrap Talos:** `task bootstrap:talos` (takes 10+ minutes, requires cluster configuration)
- **Bootstrap Apps:** `task bootstrap:apps` (takes 10+ minutes, requires cluster and KUBECONFIG)
- **Generate Talos config:** `task talos:generate-config`
- **Reset cluster:** `task talos:reset` (destructive operation)

## Repository Structure

### Key Directories
- `kubernetes/` - All Kubernetes manifests organized by namespace
  - `kubernetes/apps/` - Application deployments
  - `kubernetes/flux/` - Flux GitOps configuration
  - `kubernetes/components/` - Reusable Kustomize components
- `talos/` - Talos Linux configuration files
- `scripts/` - Python and shell utility scripts
- `bootstrap/` - Initial bootstrap configuration
- `.taskfiles/` - Task runner definitions
- `dependencies/` - Generated dependency graphs and documentation

### Important Files
- `.mise.toml` - Tool version management
- `Taskfile.yaml` - Task runner configuration
- `.sops.yaml` - SOPS encryption configuration
- `requirements.txt` - Python dependencies
- `.github/workflows/` - CI/CD pipelines

### Configuration Files
- `cluster.yaml` and `nodes.yaml` - Cluster configuration templates
- `talconfig.yaml` - Talos cluster configuration
- `helmfile.yaml` - Helm chart management
- Various `kustomization.yaml` files for Kubernetes resource management

## Common Tasks

### Development Workflow
1. **Setup:** Install tools via mise or manually
2. **Validate:** Run schema and dependency checks
3. **Test:** Use GitHub Actions for manifest validation
4. **Deploy:** Use Flux GitOps for cluster updates

### Troubleshooting
- **Schema issues:** Run `python3 scripts/fix-schemas.py` to identify and fix schema problems
- **Dependencies:** Check generated graphs in `dependencies/` directory
- **Flux issues:** Use `task reconcile` to force Flux synchronization
- **Validation:** Check `.github/workflows/flux-local.yaml` for CI validation steps

## Limitations in CI/Development

- **No actual cluster:** Most task commands require a live Talos cluster
- **Network dependencies:** Some tools require internet access for downloads
- **External services:** Integration with Cloudflare, Bitwarden, etc. requires credentials
- **Hardware specific:** Talos configuration is hardware/infrastructure specific

Always test schema validation and dependency generation scripts as these work without cluster infrastructure and catch most common errors.