```mermaid
---
config:
  layout: elk
---
flowchart LR

  subgraph "ns: dev"
    dev/gitea-runner
    dev/wikijs
  end
  external-secrets/external-secrets-stores --> dev/wikijs
  storage/volsync --> dev/gitea-runner
```
