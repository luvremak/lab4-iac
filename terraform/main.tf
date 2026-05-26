# Terraform configuration for Lab 4 — IaC.
#
# Provisions two KVM/libvirt VMs from an Ubuntu cloud image:
#   * db      — PostgreSQL database
#   * worker  — nginx reverse proxy + FastAPI application
#
# Both VMs join an isolated libvirt network. SSH keys for ansible/teacher/operator
# are baked in via cloud-init. After `terraform apply` the IPs are exposed as
# outputs AND written into ../ansible/inventory/hosts.yml so Ansible can run
# without any manual editing.

terraform {
  required_version = ">= 1.5"
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "= 0.8.0"
    }
  }
}

provider "libvirt" {
  uri = var.libvirt_uri
}

# ----------------------------------------------------------------------------
# Image pool and base volume.
# The cloud image is downloaded once into a persistent pool; per-VM volumes are
# clones backed by it.
# ----------------------------------------------------------------------------
resource "libvirt_pool" "lab4" {
  name = "lab4-pool"
  type = "dir"
  path   = var.pool_path
}

resource "libvirt_volume" "ubuntu_base" {
  name   = "ubuntu-24.04-base.qcow2"
  pool   = libvirt_pool.lab4.name
  source = var.cloud_image_url
  format = "qcow2"
}

# ----------------------------------------------------------------------------
# Isolated network for the two VMs (10.10.10.0/24).
# `nat` mode lets the VMs reach the internet (apt install ...), while traffic
# between them stays on the private bridge.
# ----------------------------------------------------------------------------
resource "libvirt_network" "lab4_net" {
  name      = "lab4-net"
  mode      = "nat"
  domain    = "lab4.local"
  addresses = [var.network_cidr]
  autostart = true
  dhcp {
    enabled = true
  }
}

# ----------------------------------------------------------------------------
# Per-VM disks (clones of the base image).
# ----------------------------------------------------------------------------
resource "libvirt_volume" "db_disk" {
  name           = "lab4-db.qcow2"
  pool           = libvirt_pool.lab4.name
  base_volume_id = libvirt_volume.ubuntu_base.id
  size           = var.disk_size_bytes
}

resource "libvirt_volume" "worker_disk" {
  name           = "lab4-worker.qcow2"
  pool           = libvirt_pool.lab4.name
  base_volume_id = libvirt_volume.ubuntu_base.id
  size           = var.disk_size_bytes
}

# ----------------------------------------------------------------------------
# cloud-init: SSH keys + minimal base setup.
# Each VM gets its own cloudinit disk so the hostname is correct.
# ----------------------------------------------------------------------------
resource "libvirt_cloudinit_disk" "db_init" {
  name      = "lab4-db-cloudinit.iso"
  pool      = libvirt_pool.lab4.name
  user_data = templatefile("${path.module}/templates/user-data.tpl", {
    hostname        = "db"
    ansible_pubkey  = trimspace(file(var.ansible_pubkey_path))
    teacher_pubkey  = trimspace(file(var.teacher_pubkey_path))
    operator_pubkey = trimspace(file(var.operator_pubkey_path))
  })
}

resource "libvirt_cloudinit_disk" "worker_init" {
  name      = "lab4-worker-cloudinit.iso"
  pool      = libvirt_pool.lab4.name
  user_data = templatefile("${path.module}/templates/user-data.tpl", {
    hostname        = "worker"
    ansible_pubkey  = trimspace(file(var.ansible_pubkey_path))
    teacher_pubkey  = trimspace(file(var.teacher_pubkey_path))
    operator_pubkey = trimspace(file(var.operator_pubkey_path))
  })
}

# ----------------------------------------------------------------------------
# Virtual machines.
# `wait_for_lease = true` makes terraform block until cloud-init reports an IP,
# so the inventory file below contains valid addresses.
# ----------------------------------------------------------------------------
resource "libvirt_domain" "db" {
  name      = "lab4-db"
  memory    = var.vm_memory
  vcpu      = var.vm_vcpu
  cloudinit = libvirt_cloudinit_disk.db_init.id

  network_interface {
    network_id     = libvirt_network.lab4_net.id
    hostname       = "db"
    wait_for_lease = true
  }

  disk {
    volume_id = libvirt_volume.db_disk.id
  }

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }
}

resource "libvirt_domain" "worker" {
  name      = "lab4-worker"
  memory    = var.vm_memory
  vcpu      = var.vm_vcpu
  cloudinit = libvirt_cloudinit_disk.worker_init.id

  network_interface {
    network_id     = libvirt_network.lab4_net.id
    hostname       = "worker"
    wait_for_lease = true
  }

  disk {
    volume_id = libvirt_volume.worker_disk.id
  }

  console {
    type        = "pty"
    target_type = "serial"
    target_port = "0"
  }
}

# ----------------------------------------------------------------------------
# Generate the Ansible inventory file with the real IPs.
# This runs automatically after `terraform apply`, so Ansible is ready to go.
# ----------------------------------------------------------------------------
resource "local_file" "ansible_inventory" {
  content = templatefile("${path.module}/templates/inventory.tpl", {
    db_ip            = libvirt_domain.db.network_interface[0].addresses[0]
    worker_ip        = libvirt_domain.worker.network_interface[0].addresses[0]
    ansible_ssh_key  = var.ansible_privkey_path
  })
  filename        = "${path.module}/../ansible/inventory/hosts.yml"
  file_permission = "0640"
}
