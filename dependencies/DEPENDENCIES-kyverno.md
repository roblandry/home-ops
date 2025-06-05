```mermaid
---
config:
  layout: elk
---
flowchart LR

  subgraph "ns: kyverno"
    kyverno/kyverno --> kyverno/kyverno-policies
  end
```
