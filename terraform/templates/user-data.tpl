#cloud-config
# cloud-init for VMs created by Terraform.
# Bootstraps just enough that Ansible can SSH in and take over:
#   * sets the hostname
#   * creates the 'ansible' user with the management SSH key + passwordless sudo
#   * pre-creates 'teacher' and 'operator' so Ansible's first run sees them
#     (proper sudoers/membership setup happens in the common role)
#   * disables password-based SSH

hostname: ${hostname}
fqdn: ${hostname}.lab4.local
manage_etc_hosts: true

users:
  - name: ansible
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys:
      - ${ansible_pubkey}

  - name: teacher
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys:
      - ${teacher_pubkey}

  - name: operator
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys:
      - ${operator_pubkey}

ssh_pwauth: false
disable_root: true

package_update: true
packages:
  - python3
  - python3-apt

runcmd:
  - [ systemctl, restart, ssh ]
