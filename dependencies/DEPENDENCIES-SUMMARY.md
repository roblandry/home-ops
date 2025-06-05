SOPS Secrets:
  - cert-manager/cert-manager/app
  - database/cloudnative-pg/cluster
  - default/mealie/app
  - default/plantit/app
  - external-secrets/external-secrets/stores/bitwarden
  - flux-system/flux-instance/app
  - monitor/headlamp/app
  - monitor/kube-prometheus-stack/app
  - network/external/cloudflared
  - network/external/external-dns
  - rook-ceph/rook-ceph/operator
  - services/netbox/app
  - services/pgloader/secret
  - services/vaultwarden/app

External Secrets:
  - cert-manager/cert-manager/app
  - database/cloudnative-pg/cluster
  - database/pgadmin/app
  - default/homepage/app
  - default/n8n/app
  - default/n8n/backup
  - default/nextcloud/elasticsearch
  - default/nextcloud/onlyoffice
  - monitor/gatus/secrets
  - monitor/grafana/app
  - monitor/kube-prometheus-stack/app
  - monitor/loki/app
  - monitor/thanos/app
  - monitor/unpoller/app
  - network/authentik/app
  - network/authentik/backup
  - network/external/external-dns
  - network/internal/remote-services/secrets
  - rook-ceph/rook-ceph/operator
  - services/graylog/app
  - services/graylog/elasticsearch
  - services/netbox/app
  - storage/garage-webui/app

Using Both:
  - cert-manager/cert-manager/app
  - database/cloudnative-pg/cluster
  - monitor/kube-prometheus-stack/app
  - network/external/external-dns
  - rook-ceph/rook-ceph/operator
  - services/netbox/app

Namespaces with no dependencies (no file created):
  - kube-system

HelmRelease dependsOn blocks:
  - default/echo:
      → network/cloudflared
  - flux-system/flux-instance:
      → flux-system/flux-operator
  - monitor/loki:
      → rook-ceph/rook-ceph-cluster
  - monitor/vector-agent:
      → monitor/vector-aggregator
  - rook-ceph/rook-ceph-cluster:
      → rook-ceph/rook-ceph-operator
      → storage/snapshot-controller
  - rook-ceph/rook-ceph-operator:
      → storage/snapshot-controller
