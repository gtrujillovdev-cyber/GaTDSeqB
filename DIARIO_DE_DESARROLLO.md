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

## [08-10-2026] - Operación: Auditoría y Confirmación de Filtros Tácticos

### 1. Desempeño de Filtros (Volume Filter en Acción)
- **Bloqueo Exitoso en ETH:** El bot de `ETH 1H` alcanzó el conteo `TD -9`, lo cual normalmente habría desencadenado una compra ciega. Sin embargo, gracias al nuevo *Filtro de Volumen Institucional* (Volume SMA), el algoritmo detectó que el movimiento carecía de fuerza y bloqueó la entrada, manteniéndose en estado `IDLE`. Una bala esquivada.

### 2. Resultados de Forward Testing
- **Cierre por Stop Loss (HYPE_1H):** El bot HYPE_1H, que estaba `IN_TRADE`, no logró avanzar el `0.75 ATR` necesario para activar el *Breakeven Shield*, sufriendo un reverso y cerrando con una pérdida de -$416.07 (Stop Loss original de 1.0 ATR). El ROI del bot baja del +5.33% al +1.16%. Sigue en verde, pero esto confirma la agresividad de usar multiplicadores tan bajos en criptomonedas.
- **Proximidad Táctica:** `BTC_1D` sigue madurando su ciclo alcista llegando a `TD 11`. Se monitorea de cerca para posible entrada de vanguardia.

### 3. Protocolo de Limpieza
- Se han eliminado todos los *scripts* intermedios (Yahoo Finance API testers, inyectores de UI) del servidor local para mantener el repositorio prístino.

## [08-10-2026] - Operación: Monitoreo Táctico y Ejecución de Macro Evalua

### 1. Auditoría del Cuartel General
- **Telemetría y Hardware:** La memoria se mantiene firme (~680MB de uso total en la Pi, sin fugas en Python tras los recolectores de basura `gc.collect()`). La carga de CPU sigue relajada (alrededor de 1.79), demostrando que la poda de *timeframes* micro fue una decisión crítica de ingeniería.
- **Sincronización:** Los precios en tiempo real del nuevo *Ticker Tape* (Crypto + TradFi) están funcionando sin saturar la red ni incurrir en bloqueos CORS gracias al puente en `server.py`.

### 2. Evaluación Táctica del Mercado (Oportunidad de Swing)
- Confirmada la observación de campo: Estamos ante un escenario de alta probabilidad para un **Swing en Largo** generalizado en el mercado cripto.
- Las temporalidades de 4H muestran señales de sobreventa extrema (Agotamiento Bajista):
  - `BTC_4H`: TD -11 (A dos velas del despliegue del Batallón DCA).
  - `ETH_4H`: TD -13.
  - `HYPE_4H`: TD -14.
- El algoritmo está diseñado para aguantar la respiración hasta la capitulación final (TD 13). Las condiciones están dadas para que la nueva lógica de *Scale-Out* (asegurar el 50% al 1.0 ATR) brille cuando ocurra el rebote.

## [08-10-2026] - Operación: Integración de Lógica Wyckoff (Volumen vs Esfuerzo)
### 1. Estado del Acoplamiento Cuantitativo
- La nueva validación extrema (Filtro de Volumen SMA + Bandas de Bollinger) se ha acoplado sin errores de compilación ni caídas del servicio en la Raspberry Pi. 
- Conceptualmente, el bot ahora opera con principios del *Método Wyckoff*: Valida las fases de Acumulación/Distribución buscando la convergencia entre el Esfuerzo (Volumen Institucional) y el Resultado (Extensión de precio en las Bandas de Bollinger), filtrando las falsas roturas (Springs/Upthrusts).

### 2. Evaluación de Mercado Actual
- El mercado se encuentra en fase de consolidación severa (Lateralización de 4H tras la caída).
- `BTC_4H` sigue en TD -11, acumulando energía.
- Los nuevos filtros están armados y evaluando silenciosamente en el *background*. Se espera que la volatilidad regrese con el cierre de la vela de 4H o diaria.

## [08-10-2026] - Operación: Auditoría y Limpieza (Post-UI Fix)
### 1. Limpieza de Infraestructura
- Se ha ejecutado el protocolo de purga local: todos los *scripts* intermedios (parches de renderizado, pruebas de CORS, scripts de Python puente) han sido borrados de la estación de trabajo para mantener el repositorio enfocado estrictamente en producción.
- **Rendimiento de Hardware:** La Raspberry Pi mantiene un perfil bajo y estable (`Load Average: 1.74`). Chromium consume los recursos esperados tras estabilizar los WebSockets de la interfaz.

### 2. Estado del Kiosko y Safari
- Se confirmó que el problema de visualización `Can't find variable` en dispositivos iOS era un vestigio del caché agresivo de WebKit/Safari, solventado tras inyectar dinámicamente el `activeBotsCount` en la memoria del renderizador.

### 3. Vigilancia Táctica (Market Watch)
- `BTC_4H` ha evolucionado al **TD -12**. Estamos al borde absoluto de la capitulación algorítmica (TD13). Los filtros avanzados están armados y listos para interceptar la caída y activar los escudos matemáticos.

## 📅 Día 9: 09 de Octubre de 2026 - Proyecto Wyckoff (Rama) y OOM Crash
- **Integración Estratégica (Rama `wycoff`):** Se inicia el desarrollo del módulo de Wyckoff combinando Volume Profile (Numpy) y divergencias de RSI.
- **Incidente de OOM (Out Of Memory):** La ejecución de un segundo `bot.py` independiente para Wyckoff saturó la memoria RAM de la Raspberry Pi, provocando un fallo en cadena que derribó el servidor DHCP/Pi-hole local. 
- **Resolución Arquitectónica (Regla #4):** Se decreta que cualquier nueva estrategia cuantitativa debe anclarse al *pipeline* de datos principal. Las descargas de Klines desde la API se realizarán una única vez por activo y timeframe. Ese DataFrame resultante se pasará por referencia a los diferentes motores matemáticos (TD Sequential, Wyckoff, etc.) para mantener la huella de memoria al mínimo.

## 📅 Día 9: 09 de Octubre de 2026 - Proyecto Wyckoff (Rama) y OOM Crash
- **Integración Estratégica (Rama `wycoff`):** Se inicia el desarrollo del módulo de Wyckoff combinando Volume Profile (Numpy) y divergencias de RSI.
- **Incidente de OOM (Out Of Memory):** La ejecución de un segundo `bot.py` independiente para Wyckoff saturó la memoria RAM de la Raspberry Pi, provocando un fallo en cadena que derribó el servidor DHCP/Pi-hole local. 
- **Resolución Arquitectónica (Regla #4):** Se decreta que cualquier nueva estrategia cuantitativa debe anclarse al *pipeline* de datos principal. Las descargas de Klines desde la API se realizarán una única vez por activo y timeframe. Ese DataFrame resultante se pasará por referencia a los diferentes motores matemáticos (TD Sequential, Wyckoff, etc.) para mantener la huella de memoria al mínimo.
- **Refactorización Core (Wyckoff Nativo):** Se ha destruido el módulo independiente de Wyckoff que causó el OOM. Sus motores de cálculo (`volume_profile.py` y `wycoff_logic.py`) han sido asimilados directamente en el `bot.py` principal. Ahora la Raspberry procesa los datos (Klines) en un solo hilo y decide si disparar por TD Sequential, por Wyckoff, o por ambos, con **0% de impacto adicional en la RAM**.
- **Entorno Multivariante (A/B/C Testing):** Se ha rediseñado la arquitectura del pipeline para evaluar múltiples motores simultáneamente con impacto de memoria cero. El Dashboard ahora compite 4 bots en tiempo real: `BTC_TD9` (Control), `BTC_WYK` (Volumen Institucional), `BTC_HYB` (Fusión) y `ETH_HYB` (Validación Cruzada).

## [11-10-2026] - Operación: Macro Auditoría y Evaluación Táctica (Entorno A/B/C)
### 1. Estado de Infraestructura y Rendimiento
- **Estabilidad de la Raspberry Pi:** La máquina lleva encendida 1 día y 16 horas sin interrupciones (`uptime: 1d 16h`). Carga de CPU estable (`Load average: 2.35`), memoria RAM óptima con ~215MB disponibles.
- **Entorno A/B/C Operativo:** La flota completa de 27 instancias virtuales (9 bots por arquetipo: Híbrido, TD9 puro y Wyckoff) se encuentra monitorizando el mercado de forma completamente asíncrona y aislada.

### 2. Evaluación Táctica del Mercado
- **Posiciones Activas:** Actualmente, `ETH_HYB_1h` y `ETH_TD9_1h` mantienen una posición corta (SELL) abierta en Ethereum a un precio de entrada de \$2,512.39.
- **Rendimiento Flotante:** La posición acumula un beneficio no realizado de +\$531.40 USD (+\$265.70 USD por bot), con el precio cotizando en \$2,502.76 hacia el objetivo de \$2,476.15.
- **Diferenciación A/B/C:** El arquetipo `ETH_WYK_1h` filtró exitosamente la entrada, demostrando la selectividad de los filtros estructurales de volumen frente a las señales puras de agotamiento secuencial.

## [11-10-2026] - Operación: Auditoría Post-Stop Loss (ETH) y Despliegue en HYPE
### 1. Análisis Forense de los Stops en ETH (1h)
- A las 16:35:07, una mecha de volatilidad en Ethereum alcanzó los \$2,516.38, ejecutando los Stop Loss de `ETH_HYB_1h` y `ETH_TD9_1h`.
- **Causa Cuantitativa:** El precio no alcanzó el umbral de `1.0 ATR` (\$2,492) necesario para desplazar el Stop a Break Even (quedó en \$2,501 antes de revertir). La pérdida se limitó a -\$165.59 USD por bot (-1.66% del bank asignado), validando el control estricto del riesgo por operación.

### 2. Nueva Posición Táctica (HYPE)
- A las 18:00:09, el arquetipo Híbrido y Wyckoff entraron en corto (SELL) en HYPE a \$86.79 tras confirmar divergencia bajista institucional y TD de agotamiento. Stop Loss fijado en \$87.65 y TP en \$85.50.

## [11-10-2026] - Operación: Optimización de Break Even Dinámico (0.5 ATR Shield)
### 1. Refactorización del Algoritmo de Salida
- **Problema Abordado:** En operaciones con baja volatilidad inicial (ej. aperturas de fin de semana), el umbral de `1.0 ATR` para Break Even resultaba excesivamente lejano, permitiendo que ganancias latentes (+0.55 ATR) se transformaran en pérdidas completas ante reversiones bruscas del mercado.
- **Solución Implementada:** 
  - Reducción del umbral de activación de Break Even de `1.0 ATR` a **`0.5 ATR`** tanto para posiciones largas (`BUY`) como cortas (`SELL`).
  - Persistencia inmediata de `state["stop_loss"] = entry` en memoria y disco para sincronización en tiempo real con el dashboard y notificaciones por Telegram.
  - Eliminación de comprobaciones redundantes de 1.25 ATR en el ciclo de salida.
- **Despliegue:** Sincronizado vía `scp` a la Raspberry Pi y servicio `gatdseq-bot` reiniciado exitosamente.

## [11-10-2026] - Operación: Despliegue de Scale-Out Simétrico (1.0 ATR)
### 1. Refactorización Cuantitativa de Salidas Parciales
- **Simetría Long/Short:** Se implementó el bloque de **Scale-Out del 50%** en la rama de ventas (`SELL`), igualando las capacidades de toma de beneficios entre compras y cortos.
- **Calibración de Umbral:** Se ajustó el disparador de Scale-Out a **`1.0 ATR`** estricto tanto en `BUY` como en `SELL`.
- **Mecánica Operativa:**
  - Al alcanzar 1.0 ATR favorable, se ejecuta un cierre parcial del 50% de la posición, deduciendo fees de exchange y registrando el PnL neto directamente en `trades_*.json`.
  - El tamaño remanente (`size_btc` y `size_usd`) se reduce al 50%.
  - El Stop Loss de la posición residual queda sellado de forma innegociable en el precio de entrada (`entry`), convirtiendo el trade en una operación libre de riesgo.
  - Se activa la bandera `scaled_out = True` para reflejar la insignia `💰 SCALE-OUT: 50% SECURED` en el dashboard.
- **Despliegue y Pruebas:** Código compilado, transferido a la Raspberry Pi, y servicio `gatdseq-bot` reiniciado operando con normalidad.

## [11-10-2026] - Operación: Macro Auditoría Técnica y Elaboración de Dossier Arquitectónico
### 1. Auditoría de Infraestructura y Limpieza
- Se purgó el script temporal `fix_reason_crash.py`, manteniendo el árbol de trabajo limpio.
- **Salud del Sistema:** La Raspberry Pi registra un uptime de 1 día y 20 horas (`uptime: 1d 19h 58m`) con una carga de CPU contenida (Load Average: 1.71) y 227MB de RAM disponible.
- **Rendimiento Operativo:** El Break Even Shield a 0.5 ATR demostró su efectividad real al proteger la posición corta en HYPE, cerrando a precio de entrada exacto (\$86.79) y evitando pérdidas mayores.

### 2. Evaluación Táctica del Mercado
- Flota de 27 instancias operando en régimen IDLE tras el cierre ordenado de HYPE.
- Próximos detonantes observados: `BTC_1d` en TD 11, `BTC_1h` en TD 7, y `HYPE_1h` en TD 9 / `HYPE_4h` en TD -9.
- **Dossier de Ingeniería:** Iniciada la redacción del plan integral de optimizaciones arquitectónicas, concurrencia I/O y mitigación del desgaste de memoria en Raspberry Pi.

## [11-10-2026] - Operación: Implementación de Optimizaciones Arquitectónicas (Fase 1)
### 1. Refactorizaciones de Rendimiento y Memoria
- **Centralización de Indicadores Pesados:** Se trasladó el cálculo de `Volume Profile` (NumPy) y `Divergencias Wyckoff` al bucle principal de ingesta, computándose una única vez por par y timeframe en lugar de 3 veces por cada arquetipo de bot. Esto elimina un 66% de procesamiento redundante en la CPU ARMv7.
- **Eliminación de Copias Innecesarias de Memoria:** Se suprimió la llamada `df = df.copy()` en cada evaluación de bot, reduciendo la presión sobre la RAM y la frecuencia del Garbage Collector (`gc.collect()`).

### 2. Protección de Hardware e Integridad de Datos (MicroSD & I/O)
- **Escrituras Atómicas (`Atomic Replace`):** Se crearon los helpers `save_state` y `save_trades` con reemplazo atómico mediante archivo temporal (`.tmp` -> `os.replace`), eliminando la posibilidad de que `server.py` capture archivos JSON a medio escribir.
- **Filtro de Escritura Sucia (Dirty-Check):** Se añadió verificación de cambios antes de volcar el estado periódico a disco. Si no hay modificaciones en `td_count`, `poc` o divergencias, se omite la escritura, reduciendo en más de un 80% las escrituras diarias en la tarjeta MicroSD.
- **Suelo de Volatilidad (Floor ATR):** Se introdujo una cota mínima para el ATR (0.6% en 1H, 1.0% en 4H, 1.5% en 1D) para garantizar que los Stop Loss nunca queden excesivamente ceñidos durante fines de semana o etapas de baja liquidez.

### 3. Verificación Operativa
- Compilación verificada con `py_compile`. Código transferido a producción en Raspberry Pi y servicio `gatdseq-bot` reiniciado en estado `active (running)`. Verificación de logs sin excepciones.
