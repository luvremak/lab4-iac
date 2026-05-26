# Лабораторна робота №4 — IaC: Terraform + Ansible

Декларативне розгортання багатовузлової системи з ЛР1 на двох віртуальних
машинах:

```
                  ┌─── VM worker ─────────────────────────────┐
client → nginx (:80) → web app (FastAPI, 127.0.0.1:5200)      │
                  └───────────────────────────────────────────┘
                                         │
                                         ▼ (TCP/5432, лише з worker)
                                  ┌── VM db ──┐
                                  │ PostgreSQL │
                                  └────────────┘
```

Інфраструктура (2 VM, мережа, cloud-init) піднімається **Terraform**-ом одним
запуском, конфігурація (користувачі, sudoers, PostgreSQL, застосунок, nginx,
файрвол) розгортається **Ansible**-ом одним запуском.

Варіант **N = 11**:
- V2 = `(11 % 2) + 1 = 2` → конфіг у TOML, **PostgreSQL**
- V3 = `(11 % 3) + 1 = 3` → застосунок **Simple Inventory**
- V5 = `(11 % 5) + 1 = 2` → порт застосунку **5200**

## Структура репозиторію

```
lab4-iac/
├── terraform/
│   ├── main.tf, variables.tf, outputs.tf
│   └── templates/
│       ├── user-data.tpl       cloud-init (SSH-ключі ansible/teacher/operator)
│       └── inventory.tpl       Ansible-інвентар, що генерується автоматично
├── ansible/
│   ├── ansible.cfg
│   ├── site.yml                головний плейбук
│   ├── requirements.yml        зовнішні Ansible-колекції
│   ├── inventory/              hosts.yml тут згенерує Terraform
│   ├── group_vars/all.yml
│   └── roles/
│       ├── common/             користувачі, sudoers, UFW, /home/student/gradebook
│       ├── postgres/           PostgreSQL + pg_hba (тільки worker)
│       ├── app/                FastAPI + venv + systemd + конфіг (templates)
│       └── nginx/              reverse proxy + UFW
└── docs/usage.md               детальні інструкції
```

## Вимоги до операторської машини

- **Linux хост** з підтримкою KVM (перевірити: `egrep '(vmx|svm)' /proc/cpuinfo`)
- `libvirt`, `qemu-kvm`, `virt-manager` (`sudo apt install libvirt-daemon-system qemu-kvm`)
- `terraform` ≥ 1.5
- `ansible-core` ≥ 2.16
- Зареєстрованість поточного користувача у групі `libvirt`

## Швидкий старт

### 1. Згенерувати 3 пари SSH-ключів (ansible / teacher / operator)

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/lab4_ansible
ssh-keygen -t ed25519 -N "" -f ~/.ssh/lab4_teacher
ssh-keygen -t ed25519 -N "" -f ~/.ssh/lab4_operator
```

### 2. Підняти інфраструктуру (Terraform)

```bash
cd terraform/
terraform init
terraform apply
```

Що відбудеться:
- Завантажиться офіційний Ubuntu 24.04 cloud-image
- Створиться ізольована мережа `lab4-net` (10.10.10.0/24, NAT)
- Піднімуться 2 VM: `lab4-db` та `lab4-worker`
- Cloud-init додасть користувачів ansible/teacher/operator з SSH-ключами
- `terraform` дочекається DHCP-lease для обох VM і **автоматично згенерує**
  `../ansible/inventory/hosts.yml` із реальними IP-адресами

Перевірка: `terraform output` покаже IP-адреси та готові SSH-команди.

### 3. Налаштувати систему (Ansible)

```bash
cd ../ansible/
ansible-galaxy collection install -r requirements.yml
ansible-playbook site.yml
```

Що відбудеться:
- **common** на обох VM: користувачі, sudoers (`operator` — тільки restart),
  UFW із deny-all за замовчуванням, `/home/student/gradebook` із `11`
- **postgres** на db: встановлення PG, БД `mywebapp`, користувач `mywebapp`,
  pg_hba дозволяє підключення тільки з IP worker-а, UFW порт 5432 теж
- **app** на worker: Python venv, копія коду, конфіг із IP db-вузла,
  systemd-юніт, міграція БД
- **nginx** на worker: site config з upstream на 127.0.0.1:5200, UFW порт 80

### 4. Перевірка

```bash
# IP worker-а — з terraform output
WORKER=$(cd ../terraform && terraform output -raw worker_ip)

# 1. Доступ через reverse proxy (HTML на /)
curl -s -i -H "Accept: text/html" http://$WORKER/

# 2. Створити елемент через API
curl -s -X POST -H "Content-Type: application/json" \
     -d '{"name":"Drill","quantity":5}' http://$WORKER/items

# 3. Список
curl -s http://$WORKER/items

# 4. /health/* має бути 404 (хован nginx-ом)
curl -s -o /dev/null -w "%{http_code}\n" http://$WORKER/health/alive

# 5. БД ззовні має бути недоступна
DB=$(cd ../terraform && terraform output -raw db_ip)
nc -zv -w 3 $DB 5432   # має дати "Connection refused" або timeout
```

### 5. Ідемпотентність

Повторний запуск playbook не має давати змін:

```bash
ansible-playbook site.yml
# у звіті: PLAY RECAP має показати changed=0 для обох хостів
```

## Перевірка вимог завдання

| Критерій | Як перевірено |
|---|---|
| Інфраструктура піднімається `terraform apply` | `cd terraform && terraform apply` |
| Налаштування одним `ansible-playbook` | `cd ansible && ansible-playbook site.yml` |
| Ідемпотентність | повторний запуск дає `changed=0` |
| Декларативність | усі ролі використовують модулі (`apt`, `user`, `template`, `systemd`, `lineinfile`, `blockinfile`), `command` лише там, де модуля немає (`psql --version`) |
| worker → db | `config.toml` має IP db-вузла; pg_hba дозволяє worker; UFW відкритий |
| БД заблокована ззовні | pg_hba + UFW — обидва шари обмежують 5432 на worker |
| SSH для ansible/teacher/operator | cloud-init додає ключі, common role закріплює sudoers |
| operator має обмежений sudo | sudoers фрагмент дозволяє лише `systemctl restart mywebapp/nginx` |
| /health/alive і /health/ready | endpoint-и доступні на 127.0.0.1:5200 (ready перевіряє підключення до БД) |
| /home/student/gradebook = 11 | common role створює файл із N=11 |

## Очистити середовище після здачі

```bash
cd terraform/
terraform destroy
```

Видалить обидві VM, диски, мережу. Cloud-image base залишиться в пулі для
наступного `terraform apply`.

## Детальні документи

Див. `docs/usage.md` — пошагові команди, troubleshooting, як змінювати
параметри.
