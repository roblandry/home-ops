# Node Replacement Procedure for Talos + Rook-Ceph

This guide documents the steps to safely replace a node running Talos in a Rook-Ceph cluster with Ceph OSDs. It assumes a setup involving Talos, Proxmox, and Ceph, and is written for manual execution (not as a script).

---

## 🔧 Preparation

Set your working variables:

```sh
export IP=10.0.10.122
export OSD=osd.1
export OSDID=1
export NODE=node03
```

---

## 📉 Step 1: Reweight OSD and Let Backfill Complete

```sh
kubectl -n rook-ceph exec deploy/rook-ceph-tools -- ceph osd reweight $OSD 0
watch -n 2 "kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph -s"
```

Wait for backfill and recovery to complete before proceeding.

---

## 📦 Step 2: Decommission the OSD

```sh
kubectl -n rook-ceph scale deploy rook-ceph-osd-$OSDID --replicas=0

kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph osd purge $OSDID --yes-i-really-mean-it
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph auth del $OSD
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph auth list
kubectl -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph osd crush remove $NODE
```

Again, wait for the cluster to settle into a clean state.

---

## 🖥️ Step 3: Shutdown the Node

```sh
talosctl shutdown -n $IP
```

---

## 🛠️ Step 4: Proxmox Cleanup

In the Proxmox GUI or shell:

1. **Remove** the disk from the VM
2. **Unset** "Start at boot"
3. **Remove** the node from Proxmox (if applicable):

```sh
pvecm delnode nuc0X
rm -rf /etc/pve/nodes/nuc0X
```

If this is the **last node** being removed from a 3-node cluster, manually reset `pve-cluster`:

```sh
systemctl stop pve-cluster corosync
pmxcfs -l
rm -rf /etc/corosync/* /etc/corosync/uidgid.d
rm /etc/pve/corosync.conf
killall pmxcfs
systemctl start pve-cluster
```

---

## 🧯 Step 5: Wipe the Node Disks (Live Debian USB)

Boot into a live Debian image and run:

```sh
sudo apt update && sudo apt install gdisk lvm2 -y
sudo vgremove pve -y
```

For **each disk**:

```sh
sudo sgdisk -Z /dev/DISK
sudo dd if=/dev/zero of=/dev/DISK bs=1M count=1000
```

> **⚠️ NOTE:** If using other formatting tools (e.g., GParted), **do not write a GPT partition table**. Ceph will fail to adopt the disk.

---

## 🌐 Step 6: Network and Boot Setup

- Update static IP in UniFi (if needed)
- Remove Ethernet cables temporarily
- Boot into Talos ISO

---

## 🚀 Step 7: Redeploy Talos Node

After confirming the disk is clean and Talos is booted:

```sh
talosctl apply-config --file talos/clusterconfig/kubernetes-$NODE.yaml -n $IP --insecure
```

Ensure the node joins the cluster, then monitor Ceph recovery.

---

## ✅ Final Notes

- This process assumes one OSD per node.
- Adjust variable values (`$IP`, `$NODE`, `$OSD`, `$OSDID`) for each replacement.
- Keep the cluster in `HEALTH_OK` or tolerable `HEALTH_WARN` state during transitions.
