output "db_ip" {
  description = "IP address of the db VM"
  value       = libvirt_domain.db.network_interface[0].addresses[0]
}

output "worker_ip" {
  description = "IP address of the worker VM"
  value       = libvirt_domain.worker.network_interface[0].addresses[0]
}

output "ansible_inventory" {
  description = "Path of the generated Ansible inventory file"
  value       = local_file.ansible_inventory.filename
}

output "ssh_examples" {
  description = "Ready-to-use SSH commands for both VMs"
  value = {
    ansible_to_db     = "ssh -i ${var.ansible_privkey_path} ansible@${libvirt_domain.db.network_interface[0].addresses[0]}"
    ansible_to_worker = "ssh -i ${var.ansible_privkey_path} ansible@${libvirt_domain.worker.network_interface[0].addresses[0]}"
    teacher_to_worker = "ssh -i ~/.ssh/lab4_teacher teacher@${libvirt_domain.worker.network_interface[0].addresses[0]}"
  }
}
