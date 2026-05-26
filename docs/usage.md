# Детальні інструкції — запуск і експлуатація

## Передумови

Цей документ описує, як підняти лабораторну на машині з Linux і
libvirt/KVM. Альтернативи (VirtualBox-провайдер для Terraform) теж
можливі, але потребують модифікації `terraform/main.tf` — провайдер
`dmacvicar/libvirt` тут використовується як основний, бо інтеграція
KVM з cloud-init проста і не вимагає Vagrant-обгорток.

### Перевірка апаратної підтримки KVM

```bash
egrep -c '(vmx|svm)' /proc/cpuinfo    # має бути > 0
ls /dev/kvm                            # має існувати
```

### Встановлення залежностей

```bash
sudo apt update
sudo apt install -y libvirt-daemon-system qemu-kvm virtinst bridge-utils \
                    cloud-image-utils dnsmasq-base

# додати поточного користувача в групу libvirt
sudo usermod -aG libvirt $USER
newgrp libvirt   # або просто relogin

# Terraform
sudo apt install -y wget gnupg
wget -O- https://apt.releases.hashicorp.com/gpg | \
    sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
    sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install -y terraform

# Ansible
sudo apt install -y ansible
```

## Покрокова процедура

### 1. Підготувати SSH-ключі

```bash
for who in ansible teacher operator; do
    ssh-keygen -t ed25519 -N "" -f ~/.ssh/lab4_$who -C "lab4-$who"
done
```

Результат: 6 файлів у `~/.ssh/lab4_*` (по парі на кожного користувача).
Шляхи зашиті в `terraform/variables.tf` як defaults — якщо ти зберігаєш
ключі деінде, перевизнач їх у `terraform.tfvars`.

### 2. Підняти інфраструктуру

```bash
cd terraform/
terraform init    # завантажить провайдер dmacvicar/libvirt
terraform apply   # ~3-5 хвилин: завантажує ~600 MB cloud-image
```

Після `apply`:
- `terraform output db_ip` — IP db-вузла
- `terraform output worker_ip` — IP worker-а
- `terraform output ansible_inventory` — шлях до згенерованого
  `../ansible/inventory/hosts.yml`

Перевір, що SSH працює:

```bash
ssh -i ~/.ssh/lab4_ansible ansible@$(terraform output -raw worker_ip) hostname
# має повернути: worker
```

### 3. Запустити Ansible

```bash
cd ../ansible/
ansible-galaxy collection install -r requirements.yml
ansible-playbook site.yml
```

Очікувано: ~3-5 хвилин на перший прогін. Перевір `PLAY RECAP` — обидва
хости мають `failed=0`.

Повторний запуск:

```bash
ansible-playbook site.yml
# PLAY RECAP має показати changed=0 — це і є ідемпотентність
```

### 4. Smoke-тести

```bash
WORKER=$(cd ../terraform && terraform output -raw worker_ip)

# Доступ через nginx
curl -i http://$WORKER/                                # 200, HTML
curl -X POST -H "Content-Type: application/json" \
     -d '{"name":"Hammer","quantity":3}' http://$WORKER/items   # 201
curl http://$WORKER/items                              # JSON-список

# /health/* має бути приховано nginx-ом (404)
curl -o /dev/null -w "%{http_code}\n" http://$WORKER/health/alive
curl -o /dev/null -w "%{http_code}\n" http://$WORKER/health/ready
```

### 5. Перевірка ізоляції БД

```bash
DB=$(cd ../terraform && terraform output -raw db_ip)

# З operator-машини (=ваш ноут) — БД має бути заблокована
nc -zv -w 3 $DB 5432
# очікувано: "Connection timed out" або "Connection refused"

# З worker-VM — БД має бути доступна
ssh -i ~/.ssh/lab4_ansible ansible@$WORKER \
    "nc -zv $DB 5432"
# очікувано: "succeeded!" / "open"
```

### 6. Перевірка користувачів

```bash
# ansible — повний sudo
ssh -i ~/.ssh/lab4_ansible ansible@$WORKER "sudo whoami"
# → root

# teacher — теж повний sudo
ssh -i ~/.ssh/lab4_teacher teacher@$WORKER "sudo whoami"
# → root

# operator — обмежений sudo (restart only)
ssh -i ~/.ssh/lab4_operator operator@$WORKER "sudo whoami"
# → sudo: a password is required (бо whoami не в дозволеному списку)
ssh -i ~/.ssh/lab4_operator operator@$WORKER \
    "sudo /bin/systemctl restart mywebapp.service"
# → працює без пароля
```

### 7. Перевірка /home/student/gradebook

```bash
ssh -i ~/.ssh/lab4_ansible ansible@$WORKER "cat /home/student/gradebook"
# → 11
```

## Troubleshooting

### `terraform apply` падає на завантаженні cloud-image

Якщо немає доступу до інтернету в libvirt, спочатку завантажити вручну:

```bash
mkdir -p /var/lib/libvirt/images/lab4
sudo wget -O /var/lib/libvirt/images/lab4/ubuntu-24.04-base.qcow2 \
    https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img
```

Потім у `variables.tf` поміняти `cloud_image_url` на локальний шлях
`file:///var/lib/libvirt/images/lab4/ubuntu-24.04-base.qcow2`.

### VM не отримує IP

```bash
sudo virsh net-list --all                         # lab4-net має бути active
sudo virsh net-dhcp-leases lab4-net               # подивитись lease
sudo journalctl -u libvirtd | tail -20
```

### Ansible не може підключитися

- Перевірити, що файл `inventory/hosts.yml` згенеровано Terraform-ом
- Перевірити, що SSH-ключ існує (`ls -la ~/.ssh/lab4_ansible`)
- Спробувати руками: `ssh -v -i ~/.ssh/lab4_ansible ansible@<ip>`

### postgres не запускається

```bash
ssh ansible@$DB
sudo systemctl status postgresql
sudo journalctl -u postgresql | tail -50
```

Часта проблема: VM з 1 GB RAM іноді не вистачає. Збільш `vm_memory` у
`variables.tf` до 1536 або 2048.

## Знесення

```bash
cd terraform/
terraform destroy
```

Знесе обидві VM, диски, мережу. Base-image cloud-init залишиться в пулі —
видалити вручну: `sudo virsh pool-destroy lab4-pool && sudo virsh pool-delete lab4-pool`.
