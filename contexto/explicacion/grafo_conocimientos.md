# Grafo de Conocimientos — BDA en la Nube 2026
**Medición de métricas en bases documentales: MongoDB vs PostgreSQL JSONB**

---

## 🗺️ Arquitectura General del Proyecto

```mermaid
flowchart TD
    PROYECTO["🎓 Proyecto BDA en la Nube 2026"]

    PROYECTO --> OBJETIVO["🎯 Objetivo\nMedir latencia, throughput y\nhuella de recursos bajo\ncontención de CPU/RAM"]
    PROYECTO --> MOTORES["🗄️ Motores Comparados"]
    PROYECTO --> DATASET["📦 Dataset"]
    PROYECTO --> EXPERIMENTO["🧪 Diseño Experimental"]
    PROYECTO --> TELEMETRIA["📊 Telemetría"]
    PROYECTO --> ENTREGABLES["📁 Entregables"]

    MOTORES --> MONGO["MongoDB\nlatest-stable\nWiredTiger\nColección orders"]
    MOTORES --> POSTGRES["PostgreSQL\nlatest-stable\nJSONB\nTabla orders"]

    DATASET --> D1["500,000 registros"]
    DATASET --> D2["3 niveles de anidamiento"]
    DATASET --> D3["~3 ítems por orden"]
    DATASET --> D4["synthetic_data_generator.py"]

    EXPERIMENTO --> PERFILES["⚙️ Perfiles Docker"]
    EXPERIMENTO --> QUERIES["📋 Queries"]
    EXPERIMENTO --> PROTOCOLO["🔁 Protocolo"]

    PERFILES --> PA["BASELINE\n4 CPU / 4 GB"]
    PERFILES --> PB["MEDIUM\n2 CPU / 2 GB"]
    PERFILES --> PC["SEVERE\n1 CPU / 1 GB"]

    QUERIES --> Q1["Q1: Unwind+Filter+Group\nSaturación de CPU"]
    QUERIES --> Q2["Q2: Massive Sort+Top-K\nEstrés de buffer/memoria"]

    PROTOCOLO --> CONC["Concurrencia: 1 / 10 / 50"]
    PROTOCOLO --> REPS["Repeticiones: 3"]
    PROTOCOLO --> TOTAL["Total: 108 runs\n36 celdas × 3 reps"]

    TELEMETRIA --> CADVISOR["cAdvisor\ncgroups v2"]
    TELEMETRIA --> NODEEXP["Node Exporter\nHost I/O"]
    TELEMETRIA --> PROMETHEUS["Prometheus\nscrape 1s"]

    ENTREGABLES --> E1["docker-compose.yml"]
    ENTREGABLES --> E2["benchmark_runner/"]
    ENTREGABLES --> E3["queries/"]
    ENTREGABLES --> E4["run_benchmarks.sh"]
    ENTREGABLES --> E5["resultados.csv"]
    ENTREGABLES --> E6["Reporte de métricas"]
```

---

## 🗄️ Relación Motor ↔ Queries ↔ Perfiles

```mermaid
flowchart LR
    subgraph MONGODB["MongoDB"]
        MQ1["Pipeline Q1\n$unwind + $match + $group"]
        MQ2A["Pipeline Q2\nallowDiskUse: false"]
        MQ2B["Pipeline Q2\nallowDiskUse: true"]
    end

    subgraph POSTGRESQL["PostgreSQL JSONB"]
        PQ1["SQL Q1\njsonb_array_elements\n+ GROUP BY"]
        PQ2A["SQL Q2\nwork_mem = 4MB"]
        PQ2B["SQL Q2\nwork_mem = 64MB"]
    end

    subgraph PERFILES["Perfiles Docker"]
        PA["BASELINE\n4 CPU / 4 GB"]
        PB["MEDIUM\n2 CPU / 2 GB"]
        PC["SEVERE\n1 CPU / 1 GB"]
    end

    PA --> MQ1 & MQ2A & MQ2B
    PB --> MQ1 & MQ2A & MQ2B
    PC --> MQ1 & MQ2A & MQ2B

    PA --> PQ1 & PQ2A & PQ2B
    PB --> PQ1 & PQ2A & PQ2B
    PC --> PQ1 & PQ2A & PQ2B
```

---

## 📦 Estructura del Documento JSON

```mermaid
flowchart TD
    DOC["📄 Documento order"]

    DOC --> OID["order_id\nUUID"]
    DOC --> TS["timestamp\nISO-8601"]
    DOC --> CUST["customer\nobjeto"]
    DOC --> ITEMS["items\narreglo de objetos"]
    DOC --> PAY["payment\nobjeto"]
    DOC --> META["metadata\nobjeto"]

    CUST --> CID["id"]
    CUST --> CTIER["tier"]
    CUST --> CSEG["segment"]
    CUST --> GEO["geo\nobjeto"]
    GEO --> GCOUNTRY["country"]
    GEO --> GSTATE["state"]
    GEO --> GCITY["city"]
    GEO --> GZIP["zip"]
    GEO --> GCOORDS["coordinates\nlat / lon"]

    ITEMS --> ITEM["item 1..n"]
    ITEM --> ISKU["sku"]
    ITEM --> ICAT["category"]
    ITEM --> IBRAND["brand"]
    ITEM --> IQTY["qty"]
    ITEM --> IPRICE["price"]
    ITEM --> ITAX["tax_pct"]
    ITEM --> IDISC["discounts\narreglo"]

    PAY --> PMETHOD["method"]
    PAY --> PSTATUS["status"]
    PAY --> PTXN["transaction_id"]
    PAY --> PLATENCY["gateway_latency_ms"]
    PAY --> PTOTALS["totals\nsubtotal / tax / final_total"]

    META --> MCHANNEL["channel"]
    META --> MUA["user_agent"]
    META --> MSESSION["session_id"]
    META --> MFLAGS["flags\nis_returned / is_flagged"]
```

---

## 📊 Flujo de Métricas y KPIs

```mermaid
flowchart LR
    RUNNER["⚡ benchmark_runner\nk6 / Python"] --> MOTOR["Motor\nMongoDB / PostgreSQL"]
    MOTOR --> METRICAS["Métricas de consulta\nlatency_p50/p95/p99\nthroughput_qps"]

    DOCKER["🐳 Docker cgroups v2"] --> CADVISOR["cAdvisor"]
    CADVISOR --> CPU_THROTTLE["cpu_cfs_throttled_seconds"]
    CADVISOR --> RSS["memory_rss_bytes"]
    CADVISOR --> OOM["oom_killed"]

    MOTOR --> DISK["disk_spill_detected\nEng. interno"]

    CADVISOR --> PROM["📈 Prometheus\nscrape 1s"]
    METRICAS --> CSV["📄 resultados.csv"]
    PROM --> CSV
    DISK --> CSV
    CSV --> REPORTE["📑 Reporte Final"]
```

---

## 🧪 Matriz Experimental

```mermaid
flowchart LR
    subgraph MATRIX["Matriz de 36 celdas × 3 reps = 108 runs"]
        direction LR
        subgraph M1["MongoDB"]
            MA["BASELINE\nQ1+Q2\n1·10·50"]
            MB["MEDIUM\nQ1+Q2\n1·10·50"]
            MC["SEVERE\nQ1+Q2\n1·10·50"]
        end
        subgraph P1["PostgreSQL"]
            PA2["BASELINE\nQ1+Q2\n1·10·50"]
            PB2["MEDIUM\nQ1+Q2\n1·10·50"]
            PC2["SEVERE\nQ1+Q2\n1·10·50"]
        end
    end
```

---

## ❓ Preguntas de Investigación → KPIs

```mermaid
flowchart LR
    M1Q["M1: ¿Cómo cambia\nla latencia P95/P99\nbajo contención?"]
    M2Q["M2: ¿Qué motor usa\nmejor los buffers\nantes de spill/OOM?"]
    M3Q["M3: ¿Cuál es la huella\nCPU/RAM por\n1,000 docs?"]

    M1Q --> P95["latency_p95_ms"]
    M1Q --> P99["latency_p99_ms"]
    M1Q --> THROTTLE["cpu_throttled_seconds"]

    M2Q --> SPILL["disk_spill_detected"]
    M2Q --> OOM2["oom_killed"]
    M2Q --> RSS2["memory_rss_bytes"]

    M3Q --> QPS["throughput_qps"]
    M3Q --> CPU2["cpu_throttled_seconds"]
    M3Q --> MEM["max_rss_mb / 1000 docs"]
```

---

## 💻 Entorno de Desarrollo

```mermaid
flowchart TD
    HOST["💻 Host\nWindows 10 · 32 GB RAM"]
    HOST --> WSL2["WSL2\nKernel Linux"]
    WSL2 --> DOCKER["🐳 Docker Desktop"]
    DOCKER --> CMongo["Contenedor MongoDB\n+ límites cgroups v2"]
    DOCKER --> CPG["Contenedor PostgreSQL\n+ límites cgroups v2"]
    DOCKER --> CCADVISOR["Contenedor cAdvisor"]
    DOCKER --> CPROM["Contenedor Prometheus"]
    DOCKER --> CNODEEXP["Contenedor Node Exporter"]
```
