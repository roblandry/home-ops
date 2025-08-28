```mermaid
---
config:
  layout: elk
---
flowchart LR

  subgraph "ns: utilities"
    utilities/cronjob-cnpg
  end
  external-secrets/external-secrets-stores --> utilities/cronjob-cnpg
```
