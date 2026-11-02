# Lista Verificable — Preparación del Entorno
## BDA en la Nube 2026 | Windows 10 + 32 GB RAM

> Ejecuta cada comando en PowerShell (como usuario normal, NO administrador)
> salvo que se indique lo contrario. Marca cada ítem al confirmar el resultado esperado.

---

## BLOQUE 1 — Docker y motor WSL2

### ✅ Check 1.1 — Docker está instalado
```powershell
docker --version
```
**Resultado esperado:** `Docker version 27.x.x` (o superior)

---

### ✅ Check 1.2 — Docker Desktop está corriendo
```powershell
docker info --format "Server Version: {{.ServerVersion}}"
```
**Resultado esperado:** Un número de versión (no un error de conexión).
**Si falla:** Abre Docker Desktop desde el menú inicio y espera a que el ícono de la barra de tareas deje de animarse.

---

### ✅ Check 1.3 — Docker usa motor Linux/WSL2 (EL MÁS IMPORTANTE)
```powershell
docker info --format "OSType: {{.OSType}} | Kernel: {{.KernelVersion}} | OS: {{.OperatingSystem}}"
```
**Resultado esperado:**
```
OSType: linux | Kernel: 5.15.x-microsoft-standard-WSL2 | OS: Docker Desktop
```
**Si OSType no es `linux`:** En Docker Desktop → Settings → General → activa *"Use the WSL 2 based engine"* y reinicia.

---

### ✅ Check 1.4 — Docker Compose disponible
```powershell
docker compose version
```
**Resultado esperado:** `Docker Compose version v2.x.x`

---

### ✅ Check 1.5 — Docker puede correr contenedores Linux
```powershell
docker run --rm hello-world
```
**Resultado esperado:** Mensaje `Hello from Docker!` seguido de explicación. Si aparece, Docker descarga y ejecuta imágenes Linux correctamente.

---

## BLOQUE 2 — WSL2 y cgroups v2

### ✅ Check 2.1 — WSL2 instalado y activo
```powershell
wsl --status
```
**Resultado esperado:** `Default Version: 2`

---

### ✅ Check 2.2 — Distro Linux disponible
```powershell
wsl -l -v
```
**Resultado esperado:** Al menos una distro con `VERSION = 2` y `STATE = Running` o `Stopped`.
Ejemplo:
```
  NAME            STATE           VERSION
* Ubuntu-22.04    Running         2
```

---

### ✅ Check 2.3 — cgroups v2 activo (CRÍTICO para el experimento)
```powershell
wsl -e mount | Select-String "cgroup2"
```
**Resultado esperado:**
```
cgroup2 on /sys/fs/cgroup type cgroup2 (rw,nosuid,nodev,noexec,relatime)
```
**Si no aparece nada:** cgroups v2 NO está habilitado → las métricas de throttling serán inválidas.
Requiere editar `.wslconfig` (ver sección de corrección al final).

---

## BLOQUE 3 — Python y librerías

### ✅ Check 3.1 — Python 3.10 o superior
```powershell
python --version
```
**Resultado esperado:** `Python 3.10.x` o superior

---

### ✅ Check 3.2 — pip disponible
```powershell
pip --version
```
**Resultado esperado:** `pip 23.x.x` o superior

---

### ✅ Check 3.3 — Librerías del proyecto instaladas
```powershell
pip show pymongo psycopg2-binary faker tqdm
```
**Resultado esperado:** Información de cada paquete sin errores `WARNING: Package not found`.
**Si faltan:**
```powershell
pip install pymongo psycopg2-binary faker tqdm
```

---

## BLOQUE 4 — Puertos disponibles

### ✅ Check 4.1 — Puertos críticos libres
```powershell
@(27017, 5432, 9090, 8080, 9100) | ForEach-Object {
    $conn = Test-NetConnection -ComputerName localhost -Port $_ -WarningAction SilentlyContinue
    [PSCustomObject]@{ Puerto = $_; Libre = -not $conn.TcpTestSucceeded }
}
```
**Resultado esperado:** `Libre = True` para todos.
**Si alguno es False:** Identifica qué proceso lo usa con `netstat -ano | findstr :<PUERTO>` y detén ese servicio o cambia el puerto en `docker-compose.yml`.

---

## BLOQUE 5 — Espacio en disco

### ✅ Check 5.1 — Espacio disponible ≥ 20 GB
```powershell
Get-PSDrive C | Select-Object @{N="Libre_GB";E={[math]::Round($_.Free/1GB,2)}}
```
**Resultado esperado:** `Libre_GB >= 20`

---

## RESUMEN — Tabla de estado

Completa esta tabla conforme verificas cada check:

| # | Check | Comando clave | Estado |
|---|-------|--------------|--------|
| 1.1 | Docker instalado | `docker --version` | ⬜ |
| 1.2 | Docker Desktop corriendo | `docker info` | ⬜ |
| 1.3 | Motor WSL2/Linux activo | `docker info --format ...` | ⬜ |
| 1.4 | Docker Compose disponible | `docker compose version` | ⬜ |
| 1.5 | Contenedores Linux funcionan | `docker run --rm hello-world` | ⬜ |
| 2.1 | WSL2 versión 2 | `wsl --status` | ⬜ |
| 2.2 | Distro Linux disponible | `wsl -l -v` | ⬜ |
| 2.3 | cgroups v2 activo | `wsl -e mount \| grep cgroup2` | ⬜ |
| 3.1 | Python 3.10+ | `python --version` | ⬜ |
| 3.2 | pip disponible | `pip --version` | ⬜ |
| 3.3 | Librerías instaladas | `pip show pymongo ...` | ⬜ |
| 4.1 | Puertos libres | `Test-NetConnection` | ⬜ |
| 5.1 | ≥ 20 GB disco libre | `Get-PSDrive C` | ⬜ |

---

## 🔧 Corrección: Habilitar cgroups v2 (si Check 2.3 falla)

**Paso 1 — Editar `%USERPROFILE%\.wslconfig`** (PowerShell como administrador):
```powershell
notepad "$env:USERPROFILE\.wslconfig"
```
Agregar o editar:
```ini
[wsl2]
kernelCommandLine = cgroup_no_v1=all systemd.unified_cgroup_hierarchy=1
```

**Paso 2 — Dentro de Ubuntu WSL2:**
```bash
sudo nano /etc/wsl.conf
```
Agregar:
```ini
[boot]
systemd=true
```

**Paso 3 — Reiniciar WSL2:**
```powershell
wsl --shutdown
```
Luego abrir Ubuntu de nuevo y volver a ejecutar el Check 2.3.

