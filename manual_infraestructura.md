# 🏛️ Manual de Infraestructura y Despliegue Distribuido: GaTDSEQ

Este documento detalla la arquitectura técnica, topología de red mesh, especificaciones de hardware, perfiles de energía, mecanismos de auto-curación y directrices de ciberseguridad sobre las que opera el ecosistema de trading cuantitativo **GaTDSEQ**.

El diseño responde a cuatro principios institucionales:
1. **Alta Disponibilidad 24/7 (Zero Downtime):** Ejecución ininterrumpida de bots en hardware dedicado.
2. **Arquitectura Híbrida Edge-Worker:** Desacoplamiento total entre la ejecución ligera en tiempo real (Edge) y el cómputo matemático intensivo de Machine Learning y optimizaciones (Worker).
3. **Cero Superficie de Exposición Pública (Zero-Trust):** Cero puertos abiertos en el router doméstico (Zero Port Forwarding); comunicaciones 100% cifradas de extremo a extremo mediante Tailscale (WireGuard).
4. **Auto-Curación de Hardware (Self-Healing):** Rutinas automáticas de purga de memoria inactiva, reinicio preventivo desatendido y protección térmica del hardware.

---

## 📑 Índice de Contenidos
1. [Topología de Red Mesh y Mapeo RFC 1123](#1-topología-de-red-mesh-y-mapeo-rfc-1123)
2. [Matriz de Nodos Físicos y Roles](#2-matriz-de-nodos-físicos-y-roles)
   - [Nodo 1: Edge Production Core (Raspberry Pi 3B)](#21-nodo-1-edge-production-core-raspberry-pi-3b)
   - [Nodo 2: High-Performance Compute Worker (MacBook Pro)](#22-nodo-2-high-performance-compute-worker-macbook-pro)
   - [Nodo 3: Workstation & Control Plane (MacBook Air M4)](#23-nodo-3-workstation--control-plane-macbook-air-m4)
   - [Nodo 4: Mobile Ops Terminal (iPhone 16 / iSH)](#24-nodo-4-mobile-ops-terminal-iphone-16--ish)
   - [Nodo 5: Visual Kiosk Telemetry (Xiaomi TV A1 Pro)](#25-nodo-5-visual-kiosk-telemetry-xiaomi-tv-a1-pro)
3. [Suite de Auto-Curación y Mantenimiento Autónomo (Mac Worker)](#3-suite-de-auto-curación-y-mantenimiento-autónomo-mac-worker)
4. [Mecanismo de Reinicio Desatendido (Headless Bootstrap Chain)](#4-mecanismo-de-reinicio-desatendido-headless-bootstrap-chain)
5. [Pipeline Cuantitativo y Cierre de Bucle Edge-Worker](#5-pipeline-cuantitativo-y-cierre-de-bucle-edge-worker)
6. [Directrices de Ciberseguridad y SecOps (Zero-Trust Standard)](#6-directrices-de-ciberseguridad-y-secops-zero-trust-standard)
7. [Manual de Operaciones y Cheat Sheet de Comandos](#7-manual-de-operaciones-y-cheat-sheet-de-comandos)

---

## 1. Topología de Red Mesh y Mapeo RFC 1123

Toda la infraestructura se comunica a través de una malla VPN privada basada en el protocolo WireGuard sobre **Tailscale**, con resolución de nombres estandarizada bajo la norma **RFC 1123 (MagicDNS)**.

```
                              ┌────────────────────────────────────────┐
                              │     TAILSCALE PRIVATE MESH NETWORK     │
                              │       WireGuard Encrypted Tunnel       │
                              │        100.64.0.0/10 (CGNAT)           │
                              └───────────────────┬────────────────────┘
                                                  │
         ┌───────────────────────┬────────────────┼───────────────────────┬───────────────────────┐
         │                       │                │                       │                       │
         ▼                       ▼                ▼                       ▼                       ▼
┌──────────────────┐   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  EDGE CORE NODE  │   │   WORKER NODE    │ │   WORKSTATION    │ │    MOBILE OPS    │ │   WALL MONITOR   │
│ Raspberry Pi 3B  │   │   MacBook Pro    │ │  MacBook Air M4  │ │    iPhone 16     │ │  Xiaomi TV A1    │
│ gtrujillo-       │   │ gtrujillo-       │ │ gtrujillo-       │ │ iphone16         │ │ tv               │
│ raspberry-pi-3b  │   │ macbook-pro      │ │ macbook-air-m4   │ │                  │ │                  │
│ 100.95.199.1     │   │ 100.108.212.124  │ │ 100.108.32.67    │ │ 100.67.23.122    │ │ 100.90.61.47     │
├──────────────────┤   ├──────────────────┤ ├──────────────────┤ ├──────────────────┤ ├──────────────────┤
│ - 27 Bots TD-Seq │   │ - Grid Search Opt│ │ - Core Dev & Git │ │ - Terminal iSH   │ │ - Kiosk 24/7     │
│ - Flask + WS     │   │ - Parquet Engine │ │ - VNC Screen Mon │ │ - Direct Aliases │ │ - Port 5001 Full │
│ - MicroSD Shield │   │ - XGBoost Gate   │ │ - UltraGear 21:9 │ │ - Mobile Telemet │ │ - Zero Latency   │
│ - AutoClean 04:00│   │ - Self-Heal 04:30│ │ - App Firewall   │ │ - WireGuard Mesh │ │ - Dark Mode      │
└──────────────────┘   └──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘
```

### Tabla de Direccionamiento y Protocolos

| Hostname MagicDNS | IP Tailscale | Rol | SO / Plataforma | Puertos Clave |
| :--- | :--- | :--- | :--- | :--- |
| `gtrujillo-raspberry-pi-3b` | `100.95.199.1` | Edge Core (Producción) | Debian 12 (ARMv7) | `22` (SSH), `5001` (Kiosk/WS), `5900` (VNC) |
| `gtrujillo-macbook-pro` | `100.108.212.124` | Worker Node (Cómputo) | macOS 11.7.11 (x86_64) | `22` (SSH), `5900` (VNC) |
| `gtrujillo-macbook-air-m4` | `100.108.32.67` | Workstation & Control | macOS 15.x (ARM64) | `22` (SSH) |
| `iphone16` | `100.67.23.122` | Kiosko Móvil & CLI | iOS 18 (iSH Alpine) | Cliente de enlace |
| `tv` | `100.90.61.47` | Telemetría Kiosko Sala | Android TV | Cliente Web Kiosk |

---

## 2. Matriz de Nodos Físicos y Roles

### 2.1. Nodo 1: Edge Production Core (Raspberry Pi 3B)
* **Hardware:** Broadcom BCM2837 ARM Cortex-A53 (4 núcleos @ 1.2 GHz), 1 GB LPDDR2 RAM, almacenamiento MicroSD SanDisk Ultra 32 GB.
* **Sistema Operativo:** Raspberry Pi OS Lite (Debian 12 Bookworm, kernel 6.6+).
* **Función:** Ejecución continua de los 27 bots de trading cuantitativo (`bot.py`) y servicio web de telemetría en tiempo real (`server.py`).
* **Blindaje de Hardware y Almacenamiento:**
  - **ZRAM:** Memoria de intercambio swap comprimida en RAM (`lz4`), reduciendo los ciclos de escritura a la tarjeta MicroSD a casi cero.
  - **Hardening de Kernel HDMI (`drm_kms_helper.poll=0`):** Inyectado directamente en `/boot/firmware/cmdline.txt`. Desactiva permanentemente el sondeo EDID del puerto HDMI que saturaba los logs del sistema (`Xorg.0.log`) a decenas de miles de líneas por segundo.
  - **Mantenimiento Nocturno (`auto_clean.sh`):** Ejecutado por cron diariamente a las **04:00 AM**. Trunca logs de más de 50 MB, vacía cachés del kernel de Linux y fuerza el `gc.collect()` de Python.
  - **Gestión por Systemd:**
    - `gatdseq-bot.service`: Motor algorítmico (reinicio automático en caso de fallo).
    - `gatdseq-server.service`: Servidor Flask + Eventlet + Socket.IO (puerto 5001).

### 2.2. Nodo 2: High-Performance Compute Worker (MacBook Pro)
* **Hardware:** Intel Core i5-4278U (2 núcleos / 4 hilos @ 2.60 GHz, Turbo Boost 3.10 GHz), 8 GB RAM DDR3 1600 MHz, 128 GB Apple PCIe SSD (43 GB dedicados a datasets).
* **Sistema Operativo:** macOS Big Sur 11.7.11.
* **Función:** Descarga y almacenamiento de series temporales masivas en formato Parquet, simulación de backtesting vectorial, optimización combinatoria de hiperparámetros (Grid Search) y clasificador Machine Learning con XGBoost.
* **Aislamiento de Discos Externos:** El disco externo mecánico Seagate se mantiene 100% aislado para copias de Time Machine y fotos personales. Todas las operaciones cuantitativas operan sobre el SSD interno de alto rendimiento.
* **Entorno de Datos:**
  - Python 3.11.11 en virtualenv (`~/GaTDSEQ_Worker/venv`).
  - Bibliotecas matemáticas compiladas: `pandas` (3.0.6), `numpy` (2.4.6), `scipy` (1.17.1), `fastparquet` (2026.9.0), `scikit-learn` (1.9.1), `xgboost` (3.2.0).
  - OpenMP nativo: Enlace simbólico en `/usr/local/opt/libomp/lib` hacia librerías LLVM para acelerar cómputos multi-hilo en la CPU Intel Haswell.

### 2.3. Nodo 3: Workstation & Control Plane (MacBook Air M4)
* **Hardware:** Apple M4 (10 núcleos CPU / 10 núcleos GPU), 16 GB Memoria Unificada de alto ancho de banda.
* **Función:** Estación de ingeniería de software, compilación de modelos, desarrollo en Git, gestión remota de la infraestructura y visualización en monitor UltraGear 21:9.
* **Perfiles de Energía (`pmset`):**
  - **En Batería (`-b`):** `sleep 1`, reposo inmediato al bajar la tapa para maximizar la autonomía.
  - **En Corriente (`-c`):** `sleep 0`, `displaysleep 3`, manteniendo los servicios vivos y apagando únicamente la pantalla.
* **Hardening de Seguridad:** macOS Application Firewall activado permanentemente (`socketfilterfw --setglobalstate on`).

### 2.4. Nodo 4: Mobile Ops Terminal (iPhone 16 / iSH)
* **Entorno:** Aplicación **iSH Shell** (entorno de emulación x86 ejecutando Alpine Linux sobre el sandbox de iOS).
* **Resolución de Red:** Dado que el sandbox de iOS aísla `/etc/resolv.conf`, se inyectaron aliases en `/etc/hosts` para mapear las IPs de Tailscale:
  ```text
  100.108.212.124 mac
  100.95.199.1    pi
  100.108.32.67   m4
  ```
* **Persistencia SSH (`~/.ssh/config`):** Configurado con `ServerAliveInterval 15` y bindings de usuario específicos (`gabrieltrujillovallejo` y `raspberry`) para evitar cierres de sesión por inactividad al bloquear la pantalla del teléfono.

### 2.5. Nodo 5: Visual Kiosk Telemetry (Xiaomi TV A1 Pro)
* **Función:** Panel Kiosko de pared continuo. Carga directamente la interfaz en navegador web (`http://gtrujillo-raspberry-pi-3b:5001/`) con refresco WebSocket en tiempo real, latencia cero y tema de alto contraste Bloomberg Terminal.

---

## 3. Suite de Auto-Curación y Mantenimiento Autónomo (Mac Worker)

Para prevenir la degradación física del hardware del MacBook Pro operando de forma continua con la tapa cerrada (*Clamshell Mode*), se desarrolló e integró una suite de auto-curación gobernada por demonios de sistema (`LaunchDaemons`):

```
                                  [ DAEMON SCHEDULER ]
                         /Library/LaunchDaemons/com.gatdseq.maintenance.plist
                                           │
                                           │ Disparo diario a las 04:30 AM
                                           ▼
                         ┌───────────────────────────────────┐
                         │       worker_maintenance.sh       │
                         └─────────────────┬─────────────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
┌──────────────────┐             ┌──────────────────┐              ┌──────────────────┐
│   VERIFICACIÓN   │             │ PURGA Y LIMPIEZA │              │  REINICIO LIMPIO │
│ ¿Trabajo activo? │             │ - /usr/sbin/purge│              │ - /bin/sync      │
│ (ML / GridSearch)│             │ - Limpieza pyc   │              │ - shutdown -r now│
│ Si: POSPONE      │             │ - Rotación logs  │              │ Recarga limpia   │
│ No: CONTINÚA     │             │ - Telemetría     │              │ del Kernel macOS │
└──────────────────┘             └──────────────────┘              └──────────────────┘
```

### Componentes de la Suite (`scripts/`):
1. **[`worker_maintenance.sh`](scripts/worker_maintenance.sh):**
   - **Detección de Tareas Críticas:** Examina la tabla de procesos (`pgrep`) en busca de `optimize_fleet.py`, `run_backtest.py` o `xgboost_gate.py`. Si hay cómputo activo, pospone el reinicio para proteger el cálculo.
   - **Purga de Memoria Inactiva:** Ejecuta `/usr/sbin/purge`, liberando gigabytes de memoria inactiva y cachés de disco acumuladas.
   - **Limpieza de Caches:** Elimina carpetas `__pycache__`, archivos `.pyc` y archivos temporales `/tmp/*.tmp` huérfanos.
   - **Rotación Preventiva de Logs:** Trunca archivos de log superiores a 25 MB (`maintenance.log`, `tailscaled.log`).
   - **Registro Telemétrico:** Guarda en `~/GaTDSEQ_Worker/logs/maintenance.log` el Uptime, Load Average, RAM libre/inactiva, espacio en SSD y estado térmico/batería.
2. **[`com.gatdseq.maintenance.plist`](scripts/com.gatdseq.maintenance.plist):**
   - Registrado en `/Library/LaunchDaemons/` con permisos `root:wheel 644`.
   - Programa la ejecución automática del script con el flag `--reboot` todos los días a las **04:30 AM**.
3. **[`com.gatdseq.caffeinate.plist`](scripts/com.gatdseq.caffeinate.plist):**
   - Registrado como LaunchDaemon de sistema de nivel raíz (`root:wheel`).
   - Mantiene activo el binario `/usr/bin/caffeinate -s -i -m -u` permanentemente, asegurando que el Mac jamás entre en suspensión con la tapa cerrada, incluso antes de que ningún usuario inicie sesión gráfica.
4. **[`install_worker_maintenance.sh`](scripts/install_worker_maintenance.sh):**
   - Script de instalación unificada que despliega los plists, ajusta permisos y habilita `pmset -a autorestart 1` (reinicio automático por hardware ante caídas del suministro eléctrico).

---

## 4. Mecanismo de Reinicio Desatendido (Headless Bootstrap Chain)

Uno de los mayores retos en la administración de servidores macOS es lograr que un portátil reinicie de forma autónoma y vuelva a estar disponible por red sin necesidad de abrir la tapa física ni pulsar ninguna tecla.

El MacBook Pro cumple estrictamente con la **Cadena de Arranque Desatendido**:

```
[ REINICIO 04:30 AM ]
         │
         ▼
┌──────────────────┐
│   APPLE EFI/BIOS │ ──► FileVault desactivado (FileVault is Off).
└────────┬─────────┘     El kernel de macOS arranca directamente sin password de disco.
         │
         ▼
┌──────────────────┐
│  WI-FI SUBSYSTEM │ ──► Credenciales almacenadas en /Library/Keychains/System.keychain.
└────────┬─────────┘     Se asocia a DIGIFIBRA automáticamente antes del login de usuario.
         │
         ▼
┌──────────────────┐
│ LAUNCHD (ROOT)   │ ──► Carga demonios de /Library/LaunchDaemons/:
└────────┬─────────┘     1. com.tailscale.tailscaled ──► Restaura IP 100.108.212.124
         │               2. sshd (OpenSSH)          ──► Abre puerto 22 para conexiones
         │               3. com.gatdseq.caffeinate   ──► Bloquea suspensión en clamshell
         │               4. screensharing            ──► Abre puerto 5900 (VNC)
         ▼
┌──────────────────┐
│   LOGIN WINDOW   │ ──► La pantalla física permanece apagada (displaysleep 5).
│  (Cero GUI Apps) │     Sin Finder ni Safari cargados, el sistema consume solo ~1.2 GB RAM
└──────────────────┘     y opera frío (~40°C), listo para recibir conexiones SSH inmediatas.
```

---

## 5. Pipeline Cuantitativo y Cierre de Bucle Edge-Worker

El flujo de trabajo cuantitativo desacoplado conecta el poder de cálculo del MacBook Pro con la ejecución en tiempo real de la Raspberry Pi:

```
[ MACBOOK PRO (WORKER) ]                                  [ RASPBERRY PI 3B (EDGE) ]
         │                                                            │
         ▼                                                            │
┌──────────────────────────────┐                                      │
│ Ingesta OHLCV Histórico      │                                      │
│ Guardado en Parquet (SSD)    │                                      │
└──────────────┬───────────────┘                                      │
               │                                                      │
               ▼                                                      │
┌──────────────────────────────┐                                      │
│ Grid Search Paralelo         │                                      │
│ optimize_fleet.py (54 comb.) │                                      │
│ Validación de Alpha & Sharpe │                                      │
└──────────────┬───────────────┘                                      │
               │                                                      │
               ▼                                                      │
┌──────────────────────────────┐                                      │
│ Exportación de Matriz        │          rsync / SCP                 │
│ fleet_optimized.json         │ ────────────────────────────────────►│
└──────────────────────────────┘                                      ▼
                                                      ┌──────────────────────────────┐
                                                      │ bot.py (Dynamic Param Loader)│
                                                      │ Cache en memoria TTL 60s     │
                                                      │ 27 Bots calibrados en vivo   │
                                                      │ Zero Downtime en Operaciones │
                                                      └──────────────────────────────┘
```

### Resultados Empíricos Demostrados:
En las pruebas sistemáticas sobre datos reales de Binance Futures (`BTC/USDT [1h]` a 30 días):
- **Parámetros Estáticos:** PnL -$503.64, Sharpe Ratio -1.71, Max Drawdown -16.17%.
- **Parámetros Calibrados por el Worker (Break-Even a 0.5x ATR):** **PnL +$1,515.97 (+15.16%)**, **Sharpe Ratio 7.11**, **Max Drawdown -4.00%**.

---

## 6. Directrices de Ciberseguridad y SecOps (Zero-Trust Standard)

Formalizadas como directriz obligatoria en el archivo [GEMINI.md](GEMINI.md) (Regla 10):

1. **Privacidad y Credenciales (Zero Password Exposure):**
   - Prohibición estricta de escribir o solicitar contraseñas en chats de IA, scripts temporales, commits o logs.
   - Toda rotación de credenciales se realiza de forma local y privada en el terminal interactivo mediante el comando nativo `passwd`.
   - En macOS, la sincronización entre la clave de usuario y el llavero cifrado se gestiona mediante:
     ```bash
     security set-keychain-password
     ```
2. **Cero Exposición Pública (Zero Port Forwarding):**
   - Prohibido abrir puertos WAN en el router de casa.
   - El acceso remoto, la telemetría del kiosko y los túneles SSH discurren exclusivamente dentro de la red mallada cifrada de Tailscale.
3. **Hardening de Endpoints:**
   - Firewall de macOS activo en estaciones de trabajo (`socketfilterfw`).
   - Autenticación multifactor (2FA) mandatoria en el panel de control de Tailscale.

---

## 7. Manual de Operaciones y Cheat Sheet de Comandos

### Conexiones Rápidas por SSH
```bash
# Conectar al Edge Core (Raspberry Pi)
ssh raspberry@gtrujillo-raspberry-pi-3b
# (O desde iPhone iSH):
ssh pi

# Conectar al Worker Node (MacBook Pro)
ssh gabrieltrujillovallejo@gtrujillo-macbook-pro
# (O desde iPhone iSH):
ssh mac

# Conectar a la Workstation (MacBook Air M4)
ssh gabrieltrujillovallejo@gtrujillo-macbook-air-m4
# (O desde iPhone iSH):
ssh m4
```

### Verificación de Servicios en Producción (Raspberry Pi)
```bash
# Ver estado del bot algorítmico
sudo systemctl status gatdseq-bot

# Ver estado del servidor de telemetría Kiosko
sudo systemctl status gatdseq-server

# Inspeccionar logs en tiempo real
tail -f ~/GaTDSEQ/bot_unified.log
```

### Gestión de la Suite de Mantenimiento (MacBook Pro)
```bash
# Inspeccionar el log de auto-curación y telemetría
cat ~/GaTDSEQ_Worker/logs/maintenance.log

# Disparar manualmente una purga de RAM y limpieza de caches
~/GaTDSEQ_Worker/scripts/worker_maintenance.sh

# Comprobar estado de los demonios LaunchDaemon
sudo launchctl list | grep gatdseq

# Verificar estado de reposo y energía
pmset -g
```

### Macro Comandos de Asistencia en el Repositorio
* **`auditoria`:** Ejecuta limpieza de scripts temporales, escaneo de logs y RAM en producción, actualización de `DIARIO_DE_DESARROLLO.md` y push con Conventional Commits.
* **`evalua`:** Analiza los archivos `state_*.json` y `bot_unified.log`, calculando el ROI de la flota, proximidad a disparos TD9 y estado de órdenes activas.

---
*Manual de Infraestructura GaTDSEQ - Versión 2.0 (Actualizada para Topología Híbrida Edge-Worker).*
