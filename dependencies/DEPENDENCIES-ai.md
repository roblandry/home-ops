```mermaid
---
config:
  layout: elk
---
flowchart LR

  subgraph "ns: ai"
    ai/ai-k8sgpt-config
    ai/ai-k8sgpt-operator
    ai/k8sgpt/config
    ai/ai-k8sgpt-operator --> ai/ai-k8sgpt-config
  end
```
