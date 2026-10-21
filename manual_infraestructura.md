# Manual de Infraestructura y Despliegue: GaTDSEQ

Este documento detalla la arquitectura de hardware distribuido, red mesh y sistemas operativos sobre la que opera el ecosistema de trading cuantitativo **GaTDSEQ**. 

El objetivo principal es lograr **alta disponibilidad (24/7)**, **bajo consumo de recursos (Edge Computing)**, **cómputo pesado desacoplado (Worker Node)** y **acceso remoto seguro sin abrir puertos en el router** mediante una red VPN Mesh.

---

## 1. Topología del Ecosistema Distribuido

```
                           [ RED TAILSCALE MESH (WIREGUARD) ]
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            │                             │                             │
            ▼                             ▼                             ▼
 ┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
 │    EDGE CORE NODE   │       │     WORKER NODE     │       │     WORKSTATION     │
 │  Raspberry Pi 3B    │       │     MacBook Pro     │       │   MacBook Air M4    │
 │  gtrujillo-raspberry│       │  gtrujillo-macbook  │       │  gtrujillo-macbook  │
 │  -pi-3b             │       │  -pro               │       │  -air-m4            │
 │  100.95.199.1       │       │  100.108.212.124    │       │  100.108.32.67      │
 ├─────────────────────┤       ├─────────────────────┤       ├─────────────────────┤
 │ - 27 Bots TD-Seq    │       │ - Backtesting Suite │       │ - Desarrollo / Git  │
 │ - Flask + Socket.IO │       │ - Grid Search Opt.  │       │ - Monitoreo VNC     │
 │ - Producción 24/7   │       │ - Python 3.11 + ML  │       │ - Pantalla UltraGear│
 └─────────────────────┘       └─────────────────────┘       └─────────────────────┘
```

---

## 2. Nodos Físicos y Roles de Infraestructura

### 2.1. Nodo 1: Producción y Ejecución 24/7 (Edge Device)
* **Dispositivo:** Raspberry Pi 3B (Arquitectura ARM Cortex-A53).
* **Sistema Operativo:** Raspberry Pi OS (Debian 12 Bookworm).
* **Nombre Tailscale (MagicDNS):** `gtrujillo-raspberry-pi-3b` (`100.95.199.1`).
* **Rol:** Ejecución continua en tiempo real de los 27 bots de trading (`bot.py`) y servicio del Kiosko Bloomberg web vía WebSockets en el puerto `5001`.
* **Optimizaciones de Kernel y Almacenamiento:**
  - **ZRAM:** Memoria swap comprimida en RAM para proteger la tarjeta MicroSD contra desgaste de escrituras.
  - **Hardening de Kernel (`cmdline.txt`):** Parámetro `drm_kms_helper.poll=0` inyectado a nivel de firmware para evitar sondeos EDID HDMI innecesarios y prevenir desbordamiento de logs.
  - **Mantenimiento Autónomo:** Script `auto_clean.sh` programado a las 4:00 AM para purga de cachés de Linux y garbage collection de Pandas.

### 2.2. Nodo 2: Cómputo Pesado y Optimización Cuantitativa (Worker Node)
* **Dispositivo:** MacBook Pro (Intel Core i5-4278U 2C/4T @ 2.60 GHz, 8 GB RAM DDR3, 128 GB SSD).
* **Sistema Operativo:** macOS Big Sur 11.7.
* **Nombre Tailscale (MagicDNS):** `gtrujillo-macbook-pro` (`100.108.212.124`).
* **Rol:** Cómputo matemático intensivo, simulación de series temporales, barridos de hiperparámetros (Grid Search) y clasificador Machine Learning con XGBoost.
* **Configuración en Modo Servidor Autónomo (24/7 Clamshell):**
  - **`SleepDisabled 1`:** Bloqueo de reposo a nivel de kernel para permitir operatividad ininterrumpida con la tapa del portátil cerrada.
  - **`displaysleep 5`:** Apagado de pantalla tras 5 minutos de inactividad para ahorro de energía y preservación del panel LCD.
  - **Daemon `caffeinate`:** Registrado como LaunchAgent persistente en `~/Library/LaunchAgents/com.gatdseq.caffeinate.plist`.
  - **Entorno Cuantitativo:** Virtualenv aislado en Python 3.11 con soporte multi-hilo OpenMP vía LLVM (`/usr/local/opt/libomp`), `fastparquet`, `scipy` y `xgboost`.

### 2.3. Nodo 3: Estación de Control y Desarrollo (Workstation)
* **Dispositivo:** MacBook Air M4 (Apple Silicon ARM64, 16 GB Memoria Unificada).
* **Nombre Tailscale (MagicDNS):** `gtrujillo-macbook-air-m4` (`100.108.32.67`).
* **Rol:** Estación de ingeniería, control de versiones con Git, revisión del Kiosko y supervisión gráfica mediante *Compartir Pantalla* (VNC / ARD puerto 5900).
* **Perfiles de Energía (`pmset`):**
  - **Batería (`-b`):** Suspensión inmediata al bajar la tapa (`sleep 1`) para preservación total de la batería en movilidad.
  - **Corriente (`-c`):** Mantiene la conectividad viva (`sleep 0`) con apagado de pantalla a los 3 minutos (`displaysleep 3`).

---

## 3. Arquitectura de Red y SecOps (Tailscale MagicDNS)

Para operar de forma remota sin comprometer la seguridad de la red local, se prescinde totalmente de la apertura de puertos en el router doméstico (Port Forwarding):

1. **Túnel Cifrado WireGuard:** Todo el tráfico entre dispositivos viaja a través de Tailscale con autenticación por clave asimétrica.
2. **Resolución Automática MagicDNS:** Permite el direccionamiento por nombre de host sin necesidad de IPs estáticas:
   - Acceso SSH a Producción: `ssh raspberry@gtrujillo-raspberry-pi-3b`
   - Acceso SSH al Worker: `ssh gabrieltrujillovallejo@gtrujillo-macbook-pro`
   - Kiosko Bloomberg en navegador: `http://gtrujillo-raspberry-pi-3b:5001/`
   - Compartir Pantalla VNC: `vnc://gtrujillo-macbook-pro` o `vnc://gtrujillo-raspberry-pi-3b`
3. **Accesos Rápidos de Escritorio:** Accesos directos `.vncloc` configurados en el escritorio del Mac para conexión remota inmediata en 1 clic.

---

## 4. Pipeline de Operación Cuantitativa

1. **Ingesta de Datos:** Descarga de velas históricas OHLCV directamente a archivos Parquet en el SSD interno del MacBook Pro (`~/GaTDSEQ_Worker/backtesting/data/`).
2. **Optimización Sistemática (`optimize_fleet.py`):** Barrido de ATR Stop Loss, Take Profit y umbrales de Break-Even en paralelo.
3. **Despliegue a Producción:** Exportación de `fleet_optimized.json` hacia la Raspberry Pi para ajuste dinámico de los 27 bots sin tiempo de inactividad (*zero downtime*).

---
*Fin del Manual de Infraestructura.*
