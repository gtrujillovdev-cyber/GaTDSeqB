# 📖 Diario de Desarrollo: GaTDSEQ (Hedge Fund Kiosk)

Este documento registra la evolución del sistema automatizado de trading cuantitativo (GaTDSEQ) desde su creación.

## 📅 Día 1: 01 de Octubre de 2026 - El Nacimiento
- **Fundación:** Creación inicial del proyecto (`Initial commit: GaTDSEQ Shadow-Trading Monitoring System`).
- **Arquitectura Base:** Se programa el primer motor cuantitativo con integración de alertas directas hacia Telegram.
- **Documentación:** Se añade el archivo README y el Manual Técnico de Infraestructura.

## 📅 Día 2: 02 de Octubre de 2026 - Inteligencia Institucional y Kiosko
- **Arquitectura Unificada:** Se refactoriza el bot a un diseño inteligente y unificado capaz de analizar 5 timeframes simultáneamente sin devorar la memoria de la Raspberry Pi.
- **Sincronización Militar:** Se programa el bot para despertar en el segundo exacto del cierre de vela, evitando así el desvío temporal (*Time Drift*).
- **Corrección de Sesgos (Bugs Críticos Resueltos):**
  - Se corrige la paradoja temporal (*Look-ahead bias*) del Trailing Stop.
  - Se arregla el temido *Gatling Bug* (un bucle infinito en el que el bot re-compraba agresivamente sobre la misma vela).
  - Se calibra la fórmula del RSI y ATR para que las matemáticas sean matemática y visualmente idénticas a las de *TradingView* (usando Wilder's Smoothing).
- **Gestión de Riesgo:** Implementación de una "Matriz de Riesgo" dinámica que invierte más o menos capital dependiendo del timeframe y del nivel de "Convicción" del RSI.
- **Interfaz (Dashboard):** Se diseña la primera versión del Kiosko Oscuro (`lite.html`) con responsive design, optimizado para iPhone y pantallas UltraGear.
- **Seguridad y Caching:** Migración de credenciales a `.env` y creación de cachés en memoria para liberar de carga a la CPU del servidor.

## 📅 Día 3: 03 de Octubre de 2026 - Aislamiento, Portafolio y WebSockets
- **Despliegue y Aislamiento ARM:** Resolución de conflictos de arquitectura. Se reconstruye el entorno virtual (`.venv`) de forma nativa directamente dentro del procesador ARM de la Raspberry Pi.
- **Portafolio Institucional en Vivo:** Se inyecta una columna lateral en el Dashboard que calcula el valor real del patrimonio sumando activos complejos (Longs Apalancados en ETH/PEPE, Spot en MSTR/BTC), obteniendo los precios en directo desde la API de Binance y Yahoo Finance.
- **Cálculo de Patrimonio (Total PNL):** Se diseña el algoritmo matemático para mostrar la PNL combinada de todas las posiciones en un único color verde o rojo.
- **Revolución WebSockets (Tiempo Real Verdadero):**
  - Se extermina el viejo sistema de recargas automáticas que generaba parpadeos (*Polling*).
  - Se instalan `Flask-SocketIO` y el motor asíncrono `Eventlet` en el servidor, creando un "túnel" directo. Ahora la pantalla refleja milimétricamente lo que hace el bot con latencia cero.
- **Auto-Preservación (Hardware):** Se programa un *Cron Job* diario (`auto_clean.sh`) que actúa a las 4:00 AM para vaciar los cachés de Linux y liberar los Dataframes residuales de Pandas, asegurando el funcionamiento 24/7 sin colapsos de RAM.

## 📅 Día 4: 04 de Octubre de 2026 - Estrategia Dual y Optimizaciones
- **Eficiencia de Hardware Extremas:** Se instala `psutil` y se elimina la necesidad del servidor web de invocar terminales invisibles en Linux, reduciendo la carga del servidor de decenas de procesos constantes a solo 3, enfriando la Raspberry.
- **Nuevo Modo de Trading (Dual Mode):**
  - Se reescribe la lógica cuantitativa. El bot ya no es rígidamente tendencial.
  - *A Favor de Tendencia:* Usa su estrategia de siempre, persiguiendo enormes Take Profits guiados por la fuerza de la EMA200.
  - *Scalping Contra-Tendencia:* Ahora se le permite cazar agotamientos (TD9) a la contra de la tendencia principal (Ej: Short en pleno Bull Market). Para ello reduce su riesgo económico a la mitad (50%) y acerca agresivamente sus parámetros de Stop y Profit, asumiendo que solo habrá un rebote breve de 1 a 4 velas.

- **Expansión Multi-Moneda (El Verdadero Hedge Fund):**
  - Se reescribe la arquitectura del bot para analizar 3 activos simultáneamente: **BTC, ETH y HYPE**.
  - El bot pasa de vigilar 5 gráficas a **15 gráficas matemáticas** simultáneas sin impacto en la RAM (gracias al Garbage Collector de Pandas).
- **Interfaz Kiosko Avanzada y Barras de Progreso:**
  - Se añade un UI dinámico que colapsa los bots que están en "IDLE" en una sola línea elegante, evitando saturar la pantalla.
  - Cuando un bot entra en "IN_TRADE", se despliega y muestra una **barra de progreso visual (Live Trailing Bar)** calculada en el front-end con 0% de coste de CPU, que enseña a cuánta distancia exacta está el precio de tocar el Stop Loss o el Take Profit.

- **Unificación de Idioma y Net Worth Dinámico (UI):**
  - Se unificó toda la interfaz del Kiosko al inglés ("Holdings", "Recent Trades") para mantener un estándar institucional.
  - Se desarrolló un algoritmo en el frontend que consulta el Ticker de 24 horas de la API de Binance (y el cierre anterior de Yahoo Finance para MSTR) para calcular y mostrar matemáticamente la **fluctuación del portfolio en las últimas 24 horas** junto al patrimonio (Ej: `+$240.50 (+5.2%)`).

- **Estética Institucional Bloomberg (Terminal UI):**
  - Se eliminó el diseño redondeado en favor de una interfaz plana de alto contraste (Courier New, bordes cuadrados).
  - Se restringió la paleta de colores a Negro (Fondo), Ámbar (Texto/Etiquetas), Cian (Datos secundarios), Verde Neón y Rojo Puro, emulando la legendaria terminal de Bloomberg.
  - El índice de "Fear & Greed" ahora es reactivo a nivel colorimétrico según sus valores (Verde para Greed, Rojo para Fear).
- **Unrealized PNL Dinámico en tiempo real:**
  - Las tarjetas de bots activos (*IN TRADE*) ahora interceptan el flujo de precios de Binance para calcular y renderizar el Beneficio/Pérdida no realizado (`Unrealized PNL`) tanto en dólares como en ROE (%).
  - Cálculo cruzado para operaciones *Short* y *Long* en el Front-End a 0 coste de CPU para el servidor.
- **Hotfixes Críticos en Entorno de Producción:**
  - Corrección de ámbito local en variable `global TIMEFRAME` que silenciaba el bot multi-moneda.
  - Solución del *Gatling Bug* en el módulo *Counter-Trend Scalp* (renombrado de `current_price` a `current_live_price` e inyección de la variable `trigger_time` perdida en refactorizaciones pasadas).

## [2026-10-05] - Migración a Futuros, Ledger Global y Kiosko Responsivo
### Añadido
- **Apalancamiento Dinámico (Dynamic Leverage):** Se ha modificado el motor de gestión de riesgo (`bot.py`) para eliminar la restricción de límite de cuenta Spot. Ahora el sistema calcula el apalancamiento necesario (hasta un límite de seguridad de 50x) para igualar el tamaño nominal (Notional) a las métricas de riesgo exigidas por el ATR.
- **Comisiones de Futuros Perpetuos:** Se ha sustituido el coste por operación del 0.1% de Binance Spot por un **0.04%** (Taker standard en futuros), logrando que el scalping de alta frecuencia en temporalidades de 5m y 15m vuelva a ser cuantitativamente rentable.
- **ROE% en Kiosko:** El porcentaje de Unrealized PNL visible en el dashboard refleja ahora el "Return on Equity" de Futuros (PNL / Margen real retenido) en lugar de medir el rendimiento Spot.
- **Libro Mayor (Trade History Ledger):** Inyectada una tabla global en `lite.html` que agrupa el historial de los 15 bots (hasta 30 eventos recientes). El UI se ha optimizado para dispositivos móviles, condensando "Razón/PNL", truncando decimales e identificando de un vistazo eventos `OPN` (Apertura) y `CLS` (Cierre).
- **Métricas de Rendimiento:** En la cabecera principal se agregó el contador global `TOTAL TRADES`, que consolida toda la actividad del fondo, y cada caja de bot (incluso en estado `IDLE`) muestra ahora el `Bankroll` fusionado con su `ROI%` dinámico, permitiendo auditar la rentabilidad neta de cada temporalidad con un solo vistazo.
- **Estricta Estética Bloomberg:** Purgado cualquier rastro de color cian (`#00ffff`) y unificado a blanco puro (`#ffffff`) para métricas de alto contraste frente a etiquetas Ámbar (`#FFCC00`), cumpliendo rigurosamente la regla del proyecto.

## [2026-10-05] (Auditoría de Tarde) - Estabilidad del Kiosko y Telegram
### Revisión
- **Kiosko UI:** Se detectó un colapso del grid en monitores Ultra-Wide (LG UltraGear) causado por la restricción `100vh` chocando contra el crecimiento vertical del historial. Parcheado liberando el scroll (`overflow-y: auto`).
- **Telegram:** Modificada la plantilla de notificaciones de entrada de `bot.py` para reportar transparentemente el apalancamiento exacto usado en la posición.
- **Rendimiento PI:** Ejecución de auditoría confirmando 0 errores en los logs, RAM estable (~274MB libres), CPU en descanso del 65% y ninguna fuga de memoria detectada tras el último despliegue.

## [2026-10-06] (Auditoría Matutina) - Chequeo de Salud del Sistema
### Revisión
- **Rendimiento PI:** Ejecución rutinaria de auditoría. Se confirman 0 errores en los logs (`bot_unified.log`). El bot ha permanecido estable durante la noche. 
- **Recursos del Sistema:** RAM estable con 263MB libres. CPU operando holgadamente con un 66% de inactividad a pesar de mantener el Kiosko cargado ininterrumpidamente. Sin pérdidas de memoria en 22 horas de *uptime*.

## [2026-10-07] - Mantenimiento del Repositorio y Publicaciones
### Refactor \& Limpieza
- **Limpieza del Workspace:** Eliminación masiva de archivos temporales de diseño (`.png`), borradores markdown inútiles y scripts de parcheo provisionales (`patch_topbar.py`) para mantener la limpieza del proyecto.
- **Control de Versiones:** Actualización estricta del `.gitignore` para garantizar que los nuevos archivos de estado dinámicos (`portfolio.json`) y el registro centralizado (`bot_unified.log`) no contaminen el repositorio remoto, asegurando que estos archivos vivan exclusivamente en producción (Raspberry Pi).
- **Documentación Externa:** Generación de resúmenes de arquitectura y exportación de esquemas (TikZ/LaTeX) en el directorio `/linkedin post` para divulgar los retos de infraestructura abordados (memoria en ARM, WebSockets, etc.).

## [2026-10-08] - Implementación de Refuerzos DCA y Fix Anti-Bucle
- **Fix (Gatling Bug):** Se corrigió la lógica de prevención de múltiples entradas en la misma vela. El bot estaba leyendo el índice `998` del DataFrame en lugar del Timestamp UNIX real, lo que causaba que tras un trade, el bot quedara bloqueado permanentemente para ese activo. Ahora evalúa el timestamp de la vela cerrada.
- **Feat (Tactical DCA):** Se implementó un sistema de promediación de coste (Dollar Cost Averaging) al alcanzar el TD Countdown 13.
  - El sistema detecta cuando un trade activo (`IN_TRADE`) sufre una caída continuada hasta alcanzar el TD 13 (o -13).
  - En lugar de asumir el Stop Loss, inyecta un bloque de capital idéntico al riesgo original.
  - Recalcula automáticamente el **Precio Promedio de Entrada**, el nuevo **Stop Loss** y el nuevo **Take Profit**.
  - Se añadió la bandera `reinforced_13` al estado JSON para evitar compras repetitivas en la vela 13.
- **Refactor (UI & Telegram):** 
  - Se eliminaron las reglas Flexbox residuales que rompían el grid de la interfaz web, aplicando anchos absolutos con `max-height`.
  - Se tradujeron todas las notificaciones de Telegram al formato institucional (Bloomberg Aesthetic), añadiendo el símbolo del activo, el timeframe y eliminando emojis coloquiales.

## [2026-10-08] - Implementación de Refuerzos DCA y Fix Anti-Bucle
- **Fix (Gatling Bug):** Se corrigió la lógica de prevención de múltiples entradas en la misma vela. El bot estaba leyendo el índice `998` del DataFrame en lugar del Timestamp UNIX real, lo que causaba que tras un trade, el bot quedara bloqueado permanentemente para ese activo. Ahora evalúa el timestamp de la vela cerrada.
- **Feat (Tactical DCA):** Se implementó un sistema de promediación de coste (Dollar Cost Averaging) al alcanzar el TD Countdown 13.
  - El sistema detecta cuando un trade activo (`IN_TRADE`) sufre una caída continuada hasta alcanzar el TD 13 (o -13).
  - En lugar de asumir el Stop Loss, inyecta un bloque de capital idéntico al riesgo original.
  - Recalcula automáticamente el **Precio Promedio de Entrada**, el nuevo **Stop Loss** y el nuevo **Take Profit**.
  - Se añadió la bandera `reinforced_13` al estado JSON para evitar compras repetitivas en la vela 13.
- **Refactor (UI & Telegram):** 
  - Se eliminaron las reglas Flexbox residuales que rompían el grid de la interfaz web, aplicando anchos absolutos con `max-height`.
  - Se tradujeron todas las notificaciones de Telegram al formato institucional (Bloomberg Aesthetic), añadiendo el símbolo del activo, el timeframe y eliminando emojis coloquiales.

## [08-10-2026] - Operación: Cirugía de Interfaz y Lógica Quant

### 1. Reingeniería del Kiosko (Frontend UI)
- **Problema Crítico:** Las tarjetas `IN_TRADE` estaban sufriendo un *overflow* vertical masivo (llegando a >300px), lo que empujaba el timeframe de 1 día fuera del área visible de la pantalla 1080p y decapitaba la interfaz. Además, la regla de CSS Grid no se estaba aplicando al monitor Ultra-Wide LG porque estaba atrapada en el `@media` de móviles.
- **Solución Aplicada:** 
  - Extracción de la regla `.trade-stats-grid` al entorno global.
  - Creación de la clase `.active-trade-card` con compresión extrema (font-size 11px, paddings a 4px).
  - Limitación algorítmica de decimales financieros (ej: `$81,823.25` en vez de `.249`).
  - **Resultado Matemático:** Una tarjeta activa ahora ocupa exactamente 120px de alto. Si los 15 bots (5 timeframes x 3 activos) abrieran trade a la vez, ocuparían 624px, encajando a la perfección en los 750px libres de la pantalla sin scroll.

### 2. Actualización Cuantitativa y Escalado Dinámico (Backend)
- **Rollback de Risk Manager Global:** Retirado el límite de 3 trades simultáneos. En fase de *Forward Testing* competitivo, cada timeframe y activo opera como un fondo independiente con 10K USD para recopilar datos sin estar capado por sus compañeros.
- **Implementación del TD Countdown Real:** El DCA (TD 13) ahora se basa estrictamente en la matemática de Tom DeMark (cálculo sobre las últimas 2 velas post-setup 9), abandonando el modelo "capitulación infinita".
- **Escalado Dinámico del Rango Verdadero (ATR):** Para evitar la "cacería de stops" por culpa del ruido de mercado en bajas temporalidades, se inyectó un multiplicador dinámico al recibir el `raw_atr`:
  - `5m -> 2.0x ATR`
  - `15m -> 1.8x ATR`
  - `1h -> 1.5x ATR`
  - `4h -> 1.2x ATR`
  - `1d -> 1.0x ATR`
  - Como efecto dominó matemático positivo, el motor de gestión de riesgo detecta que el Stop Loss está más lejos, por lo que **reduce el apalancamiento automáticamente** para mantener la misma exposición en dólares.

### 3. Ejecución de Protocolo Macro: Auditoría
- Limpieza de scripts sucios temporales (`patch_*.py`).
- Análisis de telemetría de la Raspberry Pi: La carga de CPU ronda el 60-90% por culpa del motor de Chromium (Kiosko), lo cual es normal pero justifica plenamente nuestra decisión de usar el backend para procesar Pandas y que el Front solo pinte strings ligeras.

## [08-10-2026] - Operación: Depuración de Interfaz y Auditoría de Sistema

### 1. Actualización de Interfaz (Kiosko)
- **Eliminación de Micro-Timeframes:** Tras confirmar la desactivación del análisis de `5m` y `15m` en el backend (por exceso de ruido HFT), se ha actualizado el servidor (`server.py`) para que deje de enviar los datos vacíos al *Front-End*.
- **Impacto Visual y de Rendimiento:** El Kiosko ahora solo renderiza las 3 temporalidades de alta fiabilidad (`1h`, `4h`, `1d`). Al eliminar el 40% de las tarjetas innecesarias de la pantalla, la carga de CPU de la Raspberry Pi (motor Chromium) ha descendido drásticamente (de 90% a ~40%).

### 2. Ejecución de Protocolo Macro: Auditoría y Evaluación
- **Telemetría:** La memoria se mantiene estable y la CPU ha dejado de estrangularse gracias a la limpieza del DOM en el Kiosko.
- **Rendimiento:** Evaluados los ROIs tras la aplicación de la lógica clásica. Bots como `HYPE_1H` sostienen un `+5.33%`, pero temporales micro arrastraron pérdidas pasadas (`HYPE_4H` -9.00%) al ser cazados prematuramente antes del parche de Escalado Dinámico de ATR.
- **Proximidad a Trade:** Se observan zonas calientes en `BTC_1D` (TD 11), preparándose para un ciclo a medio plazo.
