# Prerrequisitos del Proyecto — BDA en la Nube 2026
**Ordenados por importancia · Etiquetados por complejidad**

---

## Leyenda de Complejidad

| Etiqueta | Significado |
|----------|-------------|
| 🟢 **Fácil** | Instalador gráfico o un solo comando; sin configuración adicional |
| 🟡 **Medio** | Requiere configuración manual o verificación posterior |
| 🔴 **Difícil** | Requiere editar archivos del sistema, WSL2 o parámetros de kernel |

---

## 🔴 CRÍTICOS — Sin estos, el proyecto NO puede arrancar

| Prioridad | Herramienta | Complejidad | Por qué es crítico | Cómo instalar |
|-----------|-------------|-------------|-------------------|---------------|
| **1** | **WSL2** con distro Linux (Ubuntu 22.04+) | 🟡 Medio | Backend obligatorio de Docker en Windows 10 | `wsl --install` en PowerShell como administrador |
| **2** | **Docker Desktop** 4.x+ | 🟢 Fácil | Orquesta todos los contenedores del experimento | Instalador desde docker.com |
| **3** | **cgroups v2 en WSL2** | 🔴 Difícil | Sin esto, el throttling de CPU/RAM no es medible; los KPIs más importantes quedan inválidos | Editar `.wslconfig` y `/etc/wsl.conf` dentro de Ubuntu |
| **4** | **Python 3.10+** | 🟢 Fácil | Ejecutar `synthetic_data_generator.py` y scripts de benchmark | Desde python.org o Microsoft Store |

---

## 🟡 IMPORTANTES — Sin estos, el experimento está incompleto

| Prioridad | Herramienta | Complejidad | Por qué es importante | Cómo instalar |
|-----------|-------------|-------------|----------------------|---------------|
| **5** | **pip + librerías Python** (`pymongo`, `psycopg2-binary`, `faker`, `tqdm`) | 🟢 Fácil | Conectar Python con MongoDB y PostgreSQL | `pip install pymongo psycopg2-binary faker tqdm` |
| **6** | **Puertos libres** (`27017`, `5432`, `9090`, `8080`, `9100`) | 🟡 Medio | Puertos ocupados causan fallo al iniciar contenedores | Verificar con `netstat -ano` en PowerShell |
| **7** | **Disco libre ≥ 20 GB** | 🟢 Fácil | Imágenes Docker (~3 GB) + dataset (~2 GB) + logs Prometheus | Liberar espacio o usar otra unidad |
| **8** | **Acceso a internet** | 🟢 Fácil | Descargar imágenes Docker Hub en el primer `docker compose up` | Conexión activa |

---

## 🟢 OPCIONALES — Mejoran el flujo pero tienen alternativa

| Prioridad | Herramienta | Complejidad | Para qué sirve | Alternativa |
|-----------|-------------|-------------|----------------|-------------|
| **9** | **k6** 0.49+ | 🟢 Fácil | Benchmark de carga (1/10/50 clientes) | Script Python multiproceso incluido en el repo |
| **10** | **Git** | 🟢 Fácil | Control de versiones del repositorio | Carpeta local sin Git |
| **11** | **VS Code** + extensiones Docker/Python/MongoDB | 🟢 Fácil | Edición cómoda y visualización de contenedores | Cualquier editor de texto |
| **12** | **Grafana** | 🟡 Medio | Dashboard visual de métricas en tiempo real | Análisis posterior en CSV |

---

## ⚠️ El cuello de botella real: cgroups v2 en WSL2

> Este es el único prerrequisito DIFÍCIL y el que más impacta la validez del experimento.
> Sin él, Docker no aplica throttling real y las métricas de CPU estarán vacías o incorrectas.

### Pasos para habilitarlo:

**1. Editar `%USERPROFILE%\.wslconfig`** (en Windows):
```ini
[wsl2]
kernelCommandLine = cgroup_no_v1=all systemd.unified_cgroup_hierarchy=1
```

**2. Editar `/etc/wsl.conf`** (dentro de Ubuntu en WSL2):
```ini
[boot]
systemd=true
```

**3. Reiniciar WSL2 (PowerShell):**
```powershell
wsl --shutdown
wsl
```

**4. Verificar dentro de Ubuntu:**
```bash
mount | grep cgroup2
# Debe aparecer: cgroup2 on /sys/fs/cgroup type cgroup2
```

---

## ✅ Checklist de Verificación

```
[ ] 1. WSL2 instalado con Ubuntu 22.04+
[ ] 2. Docker Desktop instalado y corriendo
[ ] 3. cgroups v2 activo (verificado con: mount | grep cgroup2)
[ ] 4. Python 3.10+ instalado
[ ] 5. pip + librerías instaladas (pymongo, psycopg2-binary, faker, tqdm)
[ ] 6. Puertos 27017, 5432, 9090, 8080, 9100 disponibles
[ ] 7. Disco libre >= 20 GB
[ ] 8. Conexion a internet activa
[ ] 9. (Opcional) k6 instalado
[ ] 10. (Opcional) Git instalado
```

