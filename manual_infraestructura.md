# Manual de Infraestructura y Despliegue: GaTDSEQ

Este documento detalla la arquitectura de hardware, red y sistema operativo sobre la que se ejecuta el sistema cuantitativo GaTDSEQ. El objetivo principal de este despliegue es lograr alta disponibilidad (24/7), bajo consumo de recursos (Edge Computing) y acceso remoto seguro sin depender de servicios Cloud (PaaS/IaaS) gestionados por terceros.

## 1. Hardware Base (Edge Device)
- **Dispositivo:** Raspberry Pi (Arquitectura ARM).
- **Sistema Operativo:** Distribución basada en Linux (Raspberry Pi OS / Debian).
- **Rol:** Servidor principal autónomo. Ejecuta tanto el demonio de análisis de mercado (Python) como el servidor web (Flask).

## 2. Optimización del Sistema Operativo (Linux)

Dado que la Raspberry Pi cuenta con recursos limitados (especialmente memoria RAM y ciclos de CPU), el entorno Linux ha sido modificado y optimizado exhaustivamente:

### 2.1. ZRAM (Compresión de Memoria)
- **Problema Inicial:** Cuelgues y cuellos de botella por falta de memoria RAM. El uso intensivo de particiones Swap tradicionales daña físicamente las tarjetas SD a largo plazo debido a la alta tasa de lectura/escritura.
- **Solución Implementada:** Activación y configuración de **ZRAM**. Esto crea un bloque de swap comprimido directamente en la memoria RAM, multiplicando la capacidad efectiva de la memoria disponible y protegiendo el almacenamiento físico.

### 2.2. Poda de Servicios y Entorno Gráfico
- **Problema Inicial:** Picos de uso de CPU que alcanzaban el 75%, amenazando la estabilidad térmica y de ejecución del *Risk Engine*.
- **Solución Implementada:** 
  - Desactivación de demonios y servicios innecesarios en segundo plano (ej. Bluetooth, servicios de impresión, etc.).
  - Restricción del entorno de escritorio. En lugar de ejecutar un gestor de ventanas completo, se utiliza un modo ligero (Kiosk Mode) para Chromium si se requiere visualización local, capando los procesos gráficos de fondo.
- **Resultado:** Reducción drástica del consumo de CPU, estabilizado en un **~10%**.

## 3. Arquitectura de Red y SecOps

Para operar de forma remota sin comprometer la seguridad de la red local, se ha prescindido totalmente de la apertura de puertos en el router (Port Forwarding).

### 3.1. Tailscale (VPN Mesh)
- Todo el tráfico de acceso se enruta a través de una red privada virtual basada en el protocolo **WireGuard** (Tailscale).
- **Acceso SSH:** Permite la conexión por terminal desde equipos autorizados (ej. MacBook Pro) a la IP interna de Tailscale (`100.x.x.x`) para realizar tareas de mantenimiento, actualizaciones de código o revisar métricas con `htop`.
- **Acceso al Dashboard:** El servidor Flask expone el panel de control (`lite.html`) en el puerto 5001, accesible de forma segura únicamente para los nodos autenticados dentro de la red Mesh.

## 4. Monitorización y Telemetría Térmica
El hardware de la Raspberry Pi es monitorizado en tiempo real por el propio sistema GaTDSEQ:
- El servidor Flask realiza llamadas directas a las utilidades de Linux (`vmstat`, `free`) y sondea el sensor térmico nativo (`/sys/class/thermal/thermal_zone0/temp`).
- Estas métricas físicas se envían al Frontend, permitiendo al administrador detectar sobrecalentamientos o fugas de memoria (Memory Leaks) directamente desde el terminal web tipo Bloomberg.

---
*Fin del Manual de Infraestructura.*
