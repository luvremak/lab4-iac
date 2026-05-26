variable "libvirt_uri" {
  description = "libvirt connection URI"
  type        = string
  default     = "qemu:///system"
}

variable "pool_path" {
  description = "Filesystem path for the libvirt storage pool"
  type        = string
  default     = "/var/lib/libvirt/images/lab4"
}

variable "cloud_image_url" {
  description = "URL to the Ubuntu cloud image (qcow2)"
  type        = string
  default     = "https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img"
}

variable "network_cidr" {
  description = "CIDR for the lab network"
  type        = string
  default     = "10.10.10.0/24"
}

variable "vm_memory" {
  description = "Memory per VM, MB"
  type        = number
  default     = 1024
}

variable "vm_vcpu" {
  description = "Number of vCPUs per VM"
  type        = number
  default     = 1
}

variable "disk_size_bytes" {
  description = "Per-VM disk size in bytes (default 10 GiB)"
  type        = number
  default     = 10737418240
}

# ----------------------------------------------------------------------------
# SSH key paths. Each user (ansible/teacher/operator) gets a separate key so
# access can be granted / revoked independently. Generate them once with:
#   ssh-keygen -t ed25519 -N "" -f ~/.ssh/lab4_ansible
#   ssh-keygen -t ed25519 -N "" -f ~/.ssh/lab4_teacher
#   ssh-keygen -t ed25519 -N "" -f ~/.ssh/lab4_operator
# ----------------------------------------------------------------------------
variable "ansible_pubkey_path" {
  description = "Path to the public SSH key for the 'ansible' user"
  type        = string
  default     = "~/.ssh/lab4_ansible.pub"
}

variable "ansible_privkey_path" {
  description = "Path to the private SSH key Ansible will use (recorded in inventory)"
  type        = string
  default     = "~/.ssh/lab4_ansible"
}

variable "teacher_pubkey_path" {
  description = "Path to the public SSH key for the 'teacher' user"
  type        = string
  default     = "~/.ssh/lab4_teacher.pub"
}

variable "operator_pubkey_path" {
  description = "Path to the public SSH key for the 'operator' user"
  type        = string
  default     = "~/.ssh/lab4_operator.pub"
}
