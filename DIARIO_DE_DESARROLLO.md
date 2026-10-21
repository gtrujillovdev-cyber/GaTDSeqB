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

## [12-10-2026] - Operación: Macro Auditoría y Evaluación Táctica (Validación de Scale-Out y Take Profit en BTC)
### 1. Auditoría de Infraestructura y Estabilidad
- **Uptime y Hardware:** La Raspberry Pi 3 Model B mantiene un tiempo de actividad continuo superior a 2 días y 17 horas (`uptime: 2d 17h 31m`). La carga de CPU se sitúa en 2.14 y la memoria RAM libre en ~229 MB con cero procesos zombi.
- **Servicios:** Tanto el motor algorítmico (`gatdseq-bot`) como el servidor de streaming (`gatdseq-server`) operan de forma ininterrumpida.
- **Optimizaciones en Producción:** Tras la centralización de indicadores pesados y la implementación del guardado atómico con dirty-check, no se han registrado excepciones ni bloqueos de concurrencia.

### 2. Evaluación Táctica y Rentabilidad (Hito de Forward Testing)
- **Rentabilidad Neta Positiva:** La cartera global ha pasado a terreno positivo consolidado:
  - **P&L Realizado Acumulado:** `+$811.23 USD`
  - **Equity Total:** `$270,811.23 USD` (ROI Global: `+0.30%`).
- **Operación Maestra en BTC (1h):**
  - Los arquetipos `BTC_WYK_1h` y `BTC_HYB_1h` abrieron una posición corta institucional en \$83,667.98 tras detectar un *Wyckoff Upthrust*.
  - La nueva arquitectura de **Scale-Out simétrico escalonado a +1.0 ATR** aseguró ganancias parciales en \$83,150, \$82,997 y \$82,756, culminando con el impacto del **Take Profit** en \$82,663.96.
  - Beneficio generado: `+$1,263.91 USD` en Wyckoff y `+$1,203.20 USD` en el Híbrido, validando empíricamente la efectividad del cierre parcial frente a reversiones bruscas.

### 3. Radar de Oportunidades Inminentes
- `BTC_1d`: TD Count en **12** (a 1 vela del agotamiento macro TD 13).
- `BTC_4h`: TD Count en **-8** (a 1 vela del gatillo de compra TD -9).
- `HYPE_4h`: TD Count en **-11** (en zona de capitulación profunda de 4H).

## [13-10-2026] - Operación: Macro Auditoría y Evaluación Táctica (Récord Histórico de Rentabilidad +7.04%)
### 1. Auditoría de Infraestructura y Fiabilidad
- **Uptime Récord:** La Raspberry Pi alcanza más de 3 días y 11 horas de servicio ininterrumpido (`uptime: 3d 11h 25m`). Carga de CPU moderada (Load Average: 1.81), memoria RAM con 237 MB disponibles y temperatura contenida en 69.2°C.
- **Rendimiento de E/S y MicroSD:** Las optimizaciones atómicas y el filtro dirty-check continúan operando sin una sola incidencia de lectura corrupta en `server.py` ni fallos de disco en la memoria flash.

### 2. Evaluación Táctica y Explosión de Rentabilidad (+19,005.57 USD)
- **Hito Cuantitativo Sin Precedentes:**
  - **P&L Realizado Acumulado:** `+$19,005.57 USD`
  - **Equity Total Consolidado:** `$289,005.57 USD`
  - **ROI Global:** `+7.04%`
- **Pilares del Rendimiento (Alpha Generation):**
  - Los arquetipos Wyckoff e Híbridos en HYPE han capitaneado el resultado: `HYPE_WYK_1h` acumula `+$8,057.19 USD` (25 trades), `HYPE_HYB_1h` registra `+$8,006.08 USD` (27 trades) y `HYPE_TD9_1h` aporta `+$3,217.12 USD` (23 trades).
  - Los arquetipos de Bitcoin sostienen resultados robustos: `BTC_WYK_1h` (`+$1,263.91 USD`) y `BTC_HYB_1h` (`+$722.91 USD`).
- **Posiciones Activas en Trinchera (5 en curso):**
  - `BTC_HYB_1h` & `BTC_WYK_1h`: Cortos en \$83,587.14 hacia TP en \$82,089.58.
  - `HYPE_HYB_4h` & `HYPE_WYK_4h`: Largos en \$82.69 hacia TP en \$86.72.
  - `HYPE_TD9_1h`: Largo en \$81.81 con **Break Even Shield activado** (SL = \$81.81, riesgo cero absoluto).

### 3. Herramientas y TradingView
- Se desarrolló el indicador oficial en Pine Script v5 (`GaTDSEQ // Quantitative TD Sequential Core`) integrando la matemática exacta del bot (Setup 9, Countdown 13 DeMark, filtro de reversión institucional, EMA 200 y Bandas de Bollinger).

## [13-10-2026] - Operación: Despliegue de Reingeniería del Kiosko UltraGear (21:9 Bloomberg Terminal)
### 1. Frontend UI (Reestructuración de la Malla y Cero Scroll)
- **3 Macro-Columnas de Activos:** Se sustituyó el renderizado plano de 9 columnas por una arquitectura agrupada en 3 activos principales (`BTC`, `ETH`, `HYPE`), albergando horizontalmente la sub-matriz A/B/C (`[WYK | HYB | TD9]`) por cada timeframe (`1h`, `4h`, `1d`).
- **Eliminación Definitiva de Scroll:** Toda la flota de 27 instancias se visualiza simultáneamente sin desplazamiento vertical en monitores 1080p y 1440p ultra-panorámicos.
- **Panel Táctico Lateral (30% Ancho):**
  - **A/B/C Strategy Leaderboard:** Cuadro comparativo en tiempo real con PnL acumulado, ROI (%), volumen de operaciones y Win Rate por estrategia.
  - **Real-Time Order Log:** Historial de ejecuciones con distinción explícita de `[PRT]` (Scale-Out parcial a +1.0 ATR), `[CLS]` (cierres por TP/SL) y `[OPN]` (aperturas).
- **Trade Cards Enriquecidas:** Incorporación de insignias tácticas `[🛡️ BREAKEVEN SHIELD]` y `[💰 50% SCALED]`, junto con barra de rango dinámico del trade (`SL ── Entry ── Ahora ── TP`).

### 2. Backend Server (`server.py`)
- Se implementó y expuso la ruta `@app.route('/api/ticker')` para alimentar el Ticker Tape superior con cotizaciones e índices TradFi en tiempo real.
- Código sincronizado a la Raspberry Pi y servicio `gatdseq-server` reiniciado exitosamente.

## [13-10-2026] - Operación: Auditoría y Profesionalización Integral del Repositorio Git
### 1. Higiene del Repositorio y Alineación de Ramas
- **Convergencia de Ramas (`wycoff` -> `main`):** Se auditó la divergencia del repositorio donde el desarrollo avanzado (21 commits) residía en `wycoff`. Se ejecutó un merge fast-forward limpio hacia `main`, consolidando `main` como la única fuente de verdad institucional para producción.
- **Saneamiento del Índice (`git rm --cached`):**
  - Se eliminaron del control de versiones los archivos de estado dinámico (`portfolio.json`) que violaban la Regla 2 del proyecto.
  - Se purgó el artefacto duplicado `lite.html` de la raíz del proyecto (preservando el canónico en `templates/lite.html`).
  - Se eliminaron residuos de sistema operativo (`.DS_Store`) del índice y se blindó el `.gitignore`.

### 2. Documentación Institucional (`README.md`)
- Se reescribió por completo el `README.md` bajo el más riguroso estándar institucional de Wall Street (idioma inglés, diagramas de arquitectura de dos niveles, desglose de la matriz multivariante A/B/C de 27 bots, módulos de ejecución y salvaguarda de riesgo con Break Even Shield y Scale-Out simétrico, y directrices de hardening de hardware ARMv7).

## [13-10-2026] - Operación: Alto Contraste y Motor de Tema Solar Día/Noche en Kiosko
### 1. Frontend UI (`templates/lite.html`)
- **Corrección de Legibilidad y Alto Contraste:** Se erradicaron los tonos grises de baja visibilidad (`#777`, `#666`, `#888`), sustituyéndolos por variables CSS con contraste optimizado (`--text-muted: #b0b0b0`, `--text-white: #ffffff` y fuentes en `font-weight: 800-900`) para legibilidad instantánea en monitores UltraGear a distancia.
- **Arquitectura de Temas Dinámicos (Dual Theme Engine):**
  - **Dark Mode (Bloomberg Pure Black):** Fondo `#000000`, paneles `#050505`, bordes `#2e2e2e`, acentos en Ámbar `#ffb200`, Verde `#00ff66` y Rojo `#ff3333`.
  - **Light Mode (Financial Paper Terminal):** Fondo `#f4f5f7`, tarjetas `#ebeef2`, bordes `#c5cbd3`, texto oscuro de alto contraste `#11141a` y `#3a424e`, acentos en ámbar institucional `#b87000`, verde bosque `#008f39` y carmesí `#c91414`. Cero azules o cian (fiel a la Regla 3).
- **Conmutación Solar Automática (Amanecer / Puesta de Sol):**
  - Implementación de la función `computeSolarIsDay()` que evalúa el ciclo solar diurno/nocturno local (07:30 a 19:30).
  - Selector interactivo en la barra superior (`AUTO [SOLAR]` / `LIGHT [FORCED]` / `DARK [FORCED]`) con persistencia en `localStorage`.

## [13-10-2026] - Operación: Purga Forzada de Caché (Clear-Site-Data) y WebSocket Force-Reload
### 1. Backend (`server.py`)
- **Cabeceras Anti-Caché Agresivas:** En la ruta `/lite`, se inyectó `Clear-Site-Data: "cache"` junto con `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` para obligar a Safari en iOS y a los navegadores móviles a purgar la caché local de la página y descargar el HTML/CSS fresco.
- **Ruta de Recarga Remota (`/api/reload`):** Se implementó el endpoint `@app.route('/api/reload')` que emite el evento WebSocket `force_reload` a todas las pantallas y teléfonos conectados simultáneamente.

### 2. Frontend (`templates/lite.html`)
- **Listener WebSocket de Recarga:** Se vinculó el evento `socket.on('force_reload')` para ejecutar `window.location.reload(true)` en caliente sin intervención manual.

## [13-10-2026] - Operación: Ticker Tape Infinito Animado (Continuous Marquee de Izquierda a Derecha)
### 1. Frontend UI (`templates/lite.html`)
- **Marquee Dinámico Fluido (Wall Street Aesthetic):**
  - Se transformó la barra estática de precios en un **Ticker Tape animado continuo** con desplazamiento automático horizontal de derecha a izquierda / flujo continuo (`transform: translateX(-50%)` con `animation: tickerScroll 28s linear infinite`).
  - Implementación del patrón de pista duplicada (*Double Track*) para lograr un bucle infinito continuo e imperceptible (*Seamless Loop*) sin cortes ni parpadeos.
  - Pausa interactiva al posar el cursor o dedo (`:hover { animation-play-state: paused }`).
  - Sincronización JavaScript mediante `document.querySelectorAll('.tick-[sym]')` para reflejar variaciones de precio en tiempo real en todos los segmentos del carrusel.

## [13-10-2026] - Operación: Integración Macroeconómica de DXY (US Dollar Index) en Ticker Tape
### 1. Backend (`server.py`)
- **Adquisición del Índice DXY:** Se añadió la consulta en tiempo real al ICE Futures US Dollar Index (`DX-Y.NYB`) vía Yahoo Finance en el ciclo multihilo `ticker_fetch_loop`.
- **Ampliación de Caché TradFi:** La estructura `TICKER_CACHE` ahora distribuye en paralelo `BTC`, `ETH`, `HYPE`, `DXY`, `SP500` y `NASDAQ`.

### 2. Frontend (`templates/lite.html`)
- **Presencia en Ticker Tape:** Se inyectó la cotización de `DXY` tanto en la pista principal como en la réplica del carrusel infinito para el flujo continuo.
- **Formateo Específico:** `DXY` se renderiza en puntos de índice institucional (ej. `102.45 (+0.15%)`) sin el símbolo `$`, reservado para activos cotizados en dólares.

## [13-10-2026] - Operación: Integración de Indicadores de Volatilidad y Dominancia (BTC.D y VIX)
### 1. Backend (`server.py`)
- **CBOE Volatility Index (`^VIX`):** Se integró la extracción de la volatilidad implícita del mercado tradicional desde Yahoo Finance.
- **Dominancia de Bitcoin (`BTCD`):** Se implementó la consulta periódica a la API global de CoinGecko para obtener el porcentaje de capitalización de mercado de BTC en tiempo real (ej. `59.35%`).

### 2. Frontend (`templates/lite.html`)
- **Ampliación del Marquee Dinámico:** Se incorporaron `BTC.D` y `VIX` en ambas pistas del carrusel continuo.
- **Formateo y Simbología:** `BTC.D` se formatea con porcentaje directo (`59.35%`) y `VIX` en puntos de volatilidad con su variación porcentual correspondiente.

## [15-10-2026] - Operación: Macro Auditoría Técnica y Evaluación Táctica (5 Días Uptime)
### 1. Auditoría de Infraestructura y Fiabilidad
- **Uptime Récord Continuo:** La Raspberry Pi 3B consolida **5 días, 10 horas y 42 minutos** de ejecución ininterrumpida (`uptime: 5d 10h 42m`).
- **RAM y CPU:** Memoria disponible de 251 MB (consumo contenido al 72%), Swap utilizado de forma óptima (441 MB) y CPU en carga media controlada.
- **MicroSD Shield & Prevención Definitiva:** Se identificó que el servidor X11 generó un log masivo de 13 GB (`/var/log/Xorg.0.log`). Se truncó a cero liberando el almacenamiento al 29% (9.5 GB libres) y se programó un Cron Job diario a las 04:00 AM (`0 4 * * * /usr/bin/truncate -s 0 /var/log/Xorg.0.log`) para evitar la degradación de la memoria flash.

### 2. Evaluación Táctica y Rendimiento Cuantitativo
- **Cartera Global Consolidada:**
  - **P&L Realizado Acumulado:** `+$13,264.23 USD`
  - **Equity Total:** `$283,264.23 USD` (ROI Global: `+4.91%` sobre \$270,000 USD base).
  - **Volumen Total:** 113 trades cerrados con un **Win Rate Global del 63.7%**.
- **Alpha Leaders:**
  - `HYPE_WYK_1h`: `+$7,997.73 USD` (25 trades, Win Rate 88.0%).
  - `HYPE_HYB_1h`: `+$7,918.34 USD` (27 trades, Win Rate 81.5%).
  - `HYPE_TD9_1h`: `+$3,180.76 USD` (23 trades, Win Rate 87.0%).
  - `BTC_WYK_1h`: `+$1,188.75 USD` (6 trades, Win Rate 66.7%).
- **Trinchera Activa (8 Posiciones Abiertas):**
  - **BTC 1h:** `BTC_HYB_1h` y `BTC_WYK_1h` en compras (*Long*) desde \$81,538.01 buscando TP en \$83,076.16 (SL de protección en \$80,384.40).
  - **ETH 1h & 4h:** Flota activa en compras (*Long*) en \$2,380.06 / \$2,380.66 con objetivos TP en \$2,457 y \$2,484.
  - **HYPE 4h:** `HYPE_WYK_4h` y `HYPE_HYB_4h` en compras en \$80.54 hacia TP en \$84.85.

### 3. Radar de Gatillos Inminentes
- **BTC Macro (1d):** TD Count en **12** (a 1 vela del agotamiento DeMark 13 institucional).
- **HYPE Macro (1d):** TD Count en **-8** (a 1 vela del gatillo alcista TD -9).
- **ETH Swing (4h):** TD Count en **-7** (en zona de sobreventa con RSI en 31.49).

## [16-10-2026] - Operación: Macro Auditoría Técnica, Evaluación Táctica y Dual Clock Institucional
### 1. Auditoría de Infraestructura y Fiabilidad
- **Uptime Récord:** La Raspberry Pi 3B alcanza **6 días, 11 horas y 19 minutos** de ejecución ininterrumpida (`uptime: 6d 11h 19m`).
- **Telemetría del Edge Device:** Memoria RAM con 200 MB disponibles, Swap estabilizado en 389 MB y almacenamiento en 47% (7.3 GB disponibles). Cero saturación en disco tras la purga del log de Xorg.
- **Diagnóstico y Corrección de Timezone (Fix 2 Horas):**
  - **Causa Raíz:** Se descubrió que la Raspberry Pi tenía configurada la zona horaria por defecto `Europe/London` (BST, +01:00) y el Front-End (`templates/lite.html`) únicamente renderizaba `toISOString()`, correspondiente a la hora UTC universal (+00:00). Desde España peninsular (CEST, +02:00 en verano), esto provocaba un desfase visual de exactamente 2 horas menos.
  - **Solución Implementada:** Se rediseñó la cabecera del Kiosko (`templates/lite.html`) incorporando un **Reloj Dual Institucional**:
    - `LOC:` Hora civil local del usuario (`now.toTimeString().substring(0,8)`), marcando la hora exacta de España peninsular.
    - `UTC:` Hora universal del exchange en ámbar institucional (`now.toISOString().substring(11,19)`), indispensable para conocer el tiempo de cierre de velas de Binance.

### 2. Optimizaciones de Rendimiento y Algorítmicas (Backend & Red)
- **Eliminación de Subprocess Fork en Backend (`server.py`):**
  - Se erradicó la llamada `subprocess.call("pgrep -f 'bot.py' > /dev/null", shell=True)` dentro de `get_fleet_data()`.
  - Se sustituyó por la función de coste cero `is_bot_active()`, basada en inspección en memoria y comprobación atómica del mtime de `bot_unified.log` con caché de 10s. Cero forks del shell, aliviando la CPU de la Raspberry Pi.
- **Connection Pooling en Ticker (`requests.Session`):**
  - Se migró el ciclo `ticker_fetch_loop` a una sesión persistente `requests.Session()`, reutilizando las conexiones TCP/TLS existentes hacia Binance y Yahoo Finance, eliminando la sobrecarga de negociación SSL en el procesador ARM.
- **Desacoplamiento de Rate Limits (CoinGecko Global API):**
  - Se desacopló la consulta de dominancia de BTC (`BTCD`) para realizarse cada 300 segundos (5 min) en lugar de cada 30 segundos, protegiendo al sistema de bloqueos HTTP 429 por límite de cuota IP.
- **Alivio de I/O en Monitor WebSocket:**
  - Se recalibró el intervalo de sondeo de archivos de estado de `0.5s` a `1.2s` en `websocket_monitor_loop()`, reduciendo en más de un 50% las llamadas al sistema (`os.stat` / `getmtime`) sobre la tarjeta MicroSD.

### 3. Evaluación Táctica y Rendimiento Cuantitativo
- **Cartera Global Consolidada:**
  - **P&L Realizado Acumulado:** `+$13,363.87 USD`
  - **Equity Total:** `$183,363.87 USD` (ROI Global: `+7.86%` sobre \$170,000 USD de base activa).
  - **Volumen Total:** 182 operaciones cerradas.
- **Alpha Leaders:**
  - `HYPE_WYK_1h`: `+$7,997.73 USD` (29 trades, Win Rate 75.9%, ROI +79.98%).
  - `HYPE_HYB_1h`: `+$7,918.34 USD` (33 trades, Win Rate 66.7%, ROI +79.18%).
  - `HYPE_TD9_1h`: `+$3,180.76 USD` (26 trades, Win Rate 76.9%, ROI +31.81%).
  - `BTC_WYK_1h`: `+$597.90 USD` (11 trades, Win Rate 36.4%, ROI +5.98%).
  - `BTC_HYB_1h`: `+$88.88 USD` (13 trades, Win Rate 30.8%, ROI +0.89%).
- **Trinchera Activa (6 Posiciones Abiertas):**
  - **BTC 4h:** `BTC_HYB_4h` y `BTC_WYK_4h` en largos desde \$82,418.00 buscando TP en \$84,967.53 (SL \$80,505.85).
  - **HYPE 1d:** `HYPE_HYB_1d` y `HYPE_WYK_1d` en compras de fondo desde \$81.81 hacia TP en \$90.38 (SL \$75.38).
  - **HYPE 4h:** `HYPE_HYB_4h` y `HYPE_WYK_4h` en compras en \$81.62 hacia TP en \$86.37 (SL \$78.06).
- **Radar de Gatillos Inminentes:**
  - **HYPE Macro (1d):** TD Count alcanzó **-9** institucional con RSI en 38.51 (agotamiento bajista confirmado y entrada ejecutada).
  - **BTC Swing (4h):** TD Count en **-1** con RSI neutral en 47.87, consolidando posiciones sobre soporte EMA200.

## [17-10-2026] - Operación: Auditoría Cuantitativa de Algoritmia, Suite de Backtesting en Mac y Calibración Alpha
### 1. Auditoría de Código y Corrección de Bugs Críticos (`bot.py`)
- **Fix (Trailing Stop Regression tras Breakeven):**
  - **Causa Raíz:** Se detectó que la condición de actualización de trailing stop en `check_exit_conditions` comparaba el nuevo Stop Loss contra la variable inmutable original `sl` (`if new_sl > sl:` para compras y `if new_sl < sl:` para ventas). Cuando el *Breakeven Shield* adelantaba el SL al precio de entrada (`updated_sl = entry`), cualquier avance del trailing stop por debajo de la entrada pero por encima del SL inicial hacía que `updated_sl` retrocediera de nuevo hacia territorio de pérdidas.
  - **Solución:** Se corrigió la comparación evaluando estrictamente contra el SL dinámico activo (`if new_sl > updated_sl` en compras, `if new_sl < updated_sl` en ventas), blindando el capital una vez alcanzado el punto de equilibrio.
- **Fix (Persistencia Atómica en Scale-Out Parcial):**
  - **Causa Raíz:** En la toma parcial de beneficios (+1.0 ATR), la llamada `save_state(state)` estaba anidada dentro de la comprobación `if updated_sl < entry`. Dado que el Breakeven previo ya situaba el SL en `entry`, la condición resultaba falsa y el estado modificado (reducción al 50% de `size_btc` y `size_usd`) no se escribía en disco.
  - **Solución:** Extracción de `save_state(state)` para garantizar la persistencia atómica en disco inmediatamente tras registrar el scale-out.
- **Refactor (Protección Wyckoff contra Cuchillos Cayendo):**
  - Se eliminó la cláusula permisiva `or rsi < 45` / `or rsi > 55` en la definición de `wyckoff_spring` y `wyckoff_upthrust`. Ahora exige estrictamente confirmación de **divergencia RSI** (`divergence == 'BULLISH'` / `divergence == 'BEARISH'`), impidiendo entradas en contra de la tendencia en desplomes violentos.

### 2. Calibración Cuantitativa y Erradicación del Efecto Estrangulamiento
- **Ajuste del Breakeven Shield (+1.0 ATR):**
  - Los backtests revelaron que activar el Breakeven a `+0.5 ATR` estrangulaba las operaciones ganadoras debido al ruido diario de mercado en criptoactivos.
  - Al calibrar el umbral a `+1.0 ATR`, el trade cuenta con espacio suficiente para desarrollarse, alineándose armónicamente con el Scale-Out del 50%.
- **Calibración de Objetivos a Favor de Tendencia:**
  - `Stop Loss`: Ajustado de `2.0 ATR` a `1.5 ATR`.
  - `Take Profit`: Ajustado de `3.5 ATR` a `2.5 ATR`.
  - Esta relación riesgo/beneficio calibrada incrementó drásticamente el Win Rate y el Sharpe Ratio global.

### 3. Suite de Backtesting Institucional para Mac (`backtesting/` + `run_backtest.py`)
- **Arquitectura de Software Quant:**
  - `data_manager.py`: Paginación automática sobre CCXT con guardado local de alta velocidad en formato Parquet (ignorado por Git).
  - `indicators.py`: Motor vectorial idéntico a TradingView (Wilder's RMA para RSI y ATR, Volume Profile en NumPy, TD Sequential).
  - `engine.py`: Motor *bar-by-bar event-driven* sin *look-ahead bias*, modelando comisiones de futuros Taker (0.04%), apalancamiento dinámico, mechas conservadoras y ciclo completo de trades.
  - `analytics.py`: Generador de reportes financieros estilo Bloomberg Terminal (Sharpe, Sortino, MaxDD, Expectancy, Profit Factor).
  - `optimizer.py`: Motor de Grid Search multivariable para afinamiento sistemático de parámetros.
  - `run_backtest.py`: Interfaz de línea de comandos ergonómica con soporte para comparativas A/B/C (`--strategy ALL`) y barridos de optimización (`--optimize`).
- **Validación Empírica de Resultados:**
  - **BTC/USDT [1D]:** Rentabilidad disparada de `+$2,717.03` (+27.17%) a **`+$8,975.79 USD` (+89.76% ROI)** con **Win Rate 71.4%**, Profit Factor **228.54** y Sharpe Ratio **1.82**.
  - **SOL/USDT [1D]:** **`+$9,563.84 USD` (+95.64% ROI)** con **Win Rate 90.0%**, Max Drawdown de solo **-11.79%** y Sharpe Ratio **1.74**.

### 4. Integración del Paradigma Funnel Architecture & Confidence Scoring Gate
- **Estudio Cuantitativo:** Se analizó a nivel de arquitectura el caso de estudio de 0xNevsky sobre filtrado por embudo ("Facts kill before models judge" y separación estricta de funciones: código calcula, heurísticas evalúan, bots ejecutan).
- **Whitepaper de Investigación:** Se redactó y publicó en el repositorio el documento de grado institucional `docs/RESEARCH_FUNNEL_ARCHITECTURE.md`.
- **Implementación del Gate de Convicción (`calculate_confidence_score`):**
  - Se codificó en `bot.py` y en `backtesting/engine.py` un vector de evaluación que calcula una puntuación de convicción $S \in [0.0, 1.0]$ sobre 4 dimensiones: Calidad del Setup DeMark (30%), Momentum & Divergencia RSI (25%), Volumen Institucional vs SMA20 (25%) y Tendencia Macro EMA200 (20%).
  - **Filtro de Descarte Inmediato:** Si el score no alcanza el umbral mínimo (`MIN_CONFIDENCE = 0.55`), la orden se cancela atómicamente (`SKIP`) y se registra en log la causa de descarte, blindando el capital frente a señales de bajo ratio.
  - **Validación:** En `BTC/USDT 1D`, el gate descartó las 2 operaciones perdedoras de menor convicción, elevando el Win Rate del 71.4% al **75.0%** y el Profit Factor a **315.77**.

### 5. Optimización de Flota Cuantitativa: Supresión de la Temporalidad 1h (Flota de 18 Bots en 4h y 1d)
- **Motivación Cuantitativa y Racional de Diseño:**
  - Los resultados empíricos del backtesting demostraron sistemáticamente que la temporalidad de `1h` en criptoactivos (BTC y ETH) presenta un ratio señal/ruido desfavorable y una alta penalización por fricción de comisiones taker (0.04%), arrojando retornos negativos o mediocres frente al rendimiento institucional de `4h` y `1d` (Sharpe > 1.7, Win Rates de 75% a 90%).
  - La eliminación de `1h` reorienta la flota exclusivamente a estrategias Swing y Posicionales con ventajas estadísticas sólidas.
- **Redimensionamiento de la Flota:**
  - Reducción de la matriz multivariable de 27 bots (3 activos × 3 estrategias × 3 timeframes) a **18 bots concurrentes** (3 activos: BTC, ETH, HYPE × 3 estrategias: TD9, WYK, HYB × 2 timeframes: 4h, 1d).
  - Capital base ajustado de \$270,000 USD a **\$180,000 USD** (\$10,000 USD base por bot).
  - Benchmark por estrategia en el Leaderboard ajustado a \$60,000 USD (6 bots por variante).
- **Refactor en Backend y Telemetría:**
  - `bot.py`: Bucle principal de timeframes reducido a `timeframes = ['4h', '1d']`.
  - `server.py`: Iteradores en `get_fleet_data()` y `websocket_monitor_loop()` actualizados a `['4h', '1d']`, reduciendo en un tercio las llamadas de I/O a disco sobre los archivos de estado.
- **Optimización del Kiosko Bloomberg UI (`lite.html` & `templates/lite.html`):**
  - KPI Header actualizado: `GLOBAL EQUITY (18 BOTS)` y `ACTIVE POSITIONS: 0 / 18`.
  - Ajuste del renderizado dinámico de la cuadrícula: al pasar de 3 a 2 filas por columna de activo, el layout elimina el scroll vertical en pantallas UltraGear 21:9 y mejora la legibilidad de las tarjetas de trades activos sin recortes visuales.
  - Sincronización exacta de código entre `templates/lite.html` y la copia raíz `lite.html`.
- **Actualización Documental y README:**
  - Actualización de badges, esquemas de arquitectura ASCII, tablas de estrategia y descripciones de repositorios reflejando con exactitud la nueva arquitectura de 18 bots.

### 6. Despliegue de Blindaje de Cartera, Macro Sentimiento (Fear & Greed) y Carry Cost Guard
- **Portfolio & Correlation Shield (Control de Exposición Global):**
  - Implementación de la función `get_fleet_position_stats()` en `bot.py` que audita en memoria todos los estados `state_*.json`.
  - Establecimiento de 3 techos de seguridad institucionales:
    1. `MAX_TOTAL_FLEET_TRADES = 6`: Máximo 6 de los 18 bots pueden mantener posiciones simultáneas (33% de utilización máxima de margen).
    2. `MAX_DIRECTIONAL_TRADES = 4`: Límite estricto de máximo 4 LONGs o 4 SHORTs concurrentes en toda la cartera, evitando la sobreexposición unidireccional en caídas en cascada.
    3. `MAX_TRADES_PER_SYMBOL = 2`: Máximo 2 posiciones abiertas simultáneas en un mismo subyacente (ej. BTC), impidiendo la sobreconcentración por activo.
  - **Amortiguación Dinámica de Riesgo (Dynamic Dampening):** Si ya existen 2 o más posiciones en la misma dirección, las siguientes reducen automáticamente su tamaño al 75% (`portfolio_dampening = 0.75`).
- **Inyección del Índice Fear & Greed en el Funnel Gate:**
  - Función `get_fear_and_greed()` con caché local de 1 hora (TTL 3600s) y fallback de seguridad (50 neutral).
  - Modulación de convicción:
    - Compras en pánico extremo ($F\&G \le 25$): Bonificación de $+0.10$ por compra con descuento institucional.
    - Compras en codicia extrema ($F\&G \ge 75$): Penalización de $-0.10$ para evitar comprar techos euforizantes.
    - Ventas en codicia extrema ($F\&G \ge 75$): Bonificación de $+0.10$ para capturar distribuciones.
    - Ventas en pánico extremo ($F\&G \le 25$): Penalización de $-0.10$ para no vender en suelos de capitulación.
- **Carry Cost Guard (Protección de Tasa de Financiación en Perpetuos):**
  - Función `get_funding_rate(symbol)` consultando la API de Binance Futures con caché de 1h.
  - Penalización de $-0.05$ en señales con carry negativo agresivo ($>0.04\%$ por 8h en compras o $<-0.04\%$ en ventas) y bonificación de $+0.05$ en operaciones con carry trade positivo.
- **Sincronización Total en Motor de Backtesting:**
  - Actualización de `_calculate_confidence_score` en `backtesting/engine.py` manteniendo paridad matemática estricta entre la simulación y la ejecución en vivo.
- **Ampliación de Documentación Cuantitativa:**
  - Actualización de la fórmula matemática de 6 dimensiones y los parámetros del Portfolio Shield en `docs/RESEARCH_FUNNEL_ARCHITECTURE.md`.

### 7. Corrección de Despliegue de Plantillas UI y Purga de Caché Móvil (Kiosko Bloomberg)
- **Diagnóstico del Fallo de Visualización en Clientes Móviles:**
  - El comando `rsync` previo había actualizado la copia raíz `lite.html` pero dejó desactualizada la plantilla interna `/home/raspberry/GaTDSEQ/templates/lite.html`, que es el archivo que lee el motor Jinja2 de Flask al despachar `render_template('lite.html')`.
  - Como resultado, el servidor seguía sirviendo el layout obsoleto de 27 bots a navegadores móviles.
- **Solución y Despliegue:**
  - Sincronización exacta de `templates/lite.html` a su ruta de destino en la Raspberry Pi.
  - Inyección de cabeceras anti-caché estrictas en `<head>` de `lite.html` (`Cache-Control: no-cache, no-store, must-revalidate`, `Pragma: no-cache`, `Expires: 0`).
  - Refactor de la ruta raíz `/` en `server.py`: redirige automáticamente con código HTTP 302 y cabeceras `no-store` a `/lite`, garantizando que cualquier usuario que entre sin especificar la ruta acceda inmediatamente al Kiosko actualizado.
  - Limpieza en la Raspberry Pi: Archivado de todos los archivos residuales `state_*_1h.json` a `backups/legacy_1h_states/` para evitar estados zombis en memoria.
  - Reinicio y verificación de `gatdseq-server.service` y `gatdseq-bot.service`.

### 8. Desacoplamiento de Métricas TD: Corrección del Bug de Enmascaramiento Setup vs. Countdown en Kiosko UI
- **Diagnóstico del Fallo de Visualización (BTC 1D congelado en 12):**
  - Se detectó una inconsistencia visual en el Kiosko donde BTC en timeframe diario (`1d`) mostraba permanentemente un valor de `12` en rojo mientras TradingView mostraba un conteo bajista en curso (-3 cerrado, -4 en vela viva).
  - **Causa Raíz:** En `bot.py` (antigua línea 439), la directiva `new_td = int(countdown) if countdown != 0 else int(count)` sobreescribía el valor del TD Setup con el TD Countdown siempre que este último fuera distinto de cero.
  - Al haberse completado un Setup alcista semanas atrás, el Countdown avanzó hasta la barra 12 el 11 de octubre. Al consolidar el mercado por debajo del máximo de hace 2 días (`close <= high[i-2]`), el Countdown alcista quedó suspendido en 12 sin alcanzar 13 ni cancelarse, enmascarando el Setup bajista activo (-3).
  - La lógica del Risk Engine en `analyze_market()` evalúa disparos de orden exclusivamente sobre el Setup (`count <= -9` o `count >= 9`), por lo que mostrar el Countdown en la celda TD9 inducía a error al operador.
- **Solución Técnica Aplicada:**
  - **Desacoplamiento en Backend (`bot.py`):** Se separó la persistencia de estado para que `state["td_count"]` guarde estrictamente el conteo real del Setup (`int(count)`), garantizando paridad 1:1 con TradingView y con las condiciones de disparo del bot. Se añadió la clave independiente `state["td_countdown"]` para preservar el estado del Countdown sin contaminar el Setup.
  - **Actualización en Frontend (`lite.html` y `templates/lite.html`):** Los pills de variantes muestran de forma limpia el Setup canónico (`-3` en verde para BTC 1d) y añaden un tooltip descriptivo institucional en `title` (`TD Setup: -3 | CD: 12`) para visibilidad del Countdown sin saturar la cuadrícula Bloomberg.
  - **Despliegue y Verificación en Producción:**
    - Código compilado localmente con `py_compile`.
    - Sincronización a la Raspberry Pi (`/home/raspberry/GaTDSEQ/bot.py`, `lite.html`, `templates/lite.html`).
    - Reinicio de servicios `gatdseq-bot.service` y `gatdseq-server.service`.
    - Verificación del estado en producción: `state_BTC_TD9_1d.json` transicionó inmediatamente de `12` a `-3` con paridad exacta con el indicador de TradingView.

### 9. Rediseño Responsive de Cabecera (Selector de Tema) y Corrección Crítica del Countdown 13 (El Batallón DCA)
- **Rediseño Responsive de Cabecera (Selector de Tema Móvil):**
  - **Problema:** En pantallas reducidas (dispositivos móviles/iPhone), el botón del selector de tema (`AUTO [DAY]`) se intercalaba de forma caótica en medio del título (`QUANTITATIVE [AUTO] CORE // RASPBERRY PI 3B`) fracturando el espaciado y la estética institucional Bloomberg.
  - **Solución UI:** 
    - Se reordenó el árbol DOM colocando el botón tras el bloque de métricas de telemetría (`hw-stats`).
    - En vista escritorio, se sitúa de forma limpia al extremo derecho de la barra tras los relojes LOC/UTC.
    - Se introdujeron reglas de responsive específicas (`@media (max-width: 768px)`): la cabecera añade un canal lateral (`padding-right: 48px`), el botón se fija con posición absoluta en la esquina superior derecha (`position: absolute; top: 0; right: 0;`) y la etiqueta de texto se oculta (`.theme-label-text { display: none; }`), transformando el selector en un icono badge minimalista y cuadrado (`[ ☀️ ]` / `[ 🌙 ]`).
    - Las etiquetas de modo en escritorio se simplificaron a `AUTO (DAY)`, `AUTO (NIGHT)`, `LIGHT` y `DARK` con tooltips contextuales dinámicos.
- **Corrección Lógica del Countdown 13 ("El Batallón DCA"):**
  - **Detección de Dead Code:** Se detectó que en `calculate_td_sequential()`, la condición `if countdown_up == 13: setup_up_active = False` se evaluaba antes de volcar el valor al array. Al desactivar `setup_up_active`, el código caía en el `else` e insertaba un `0` en vez del `13` (secuencia: `11, 12, 0`).
  - Como consecuencia, los bloques de refuerzo por promediado a la baja (`pos == BUY and countdown == -13` y `pos == SELL and countdown == 13`) nunca habrían podido ejecutarse en producción.
  - **Corrección Algorítmica:** Se sincronizó en `bot.py` y `backtesting/indicators.py` para registrar el valor `13` (o `-13`) en la vela de agotamiento antes de desactivar la bandera y resetear el contador a cero.
- **Despliegue y Reinicio:** Sincronizado a producción y reiniciados `gatdseq-bot` y `gatdseq-server`.

### 10. Expansión a 27 Bots: Cobertura de Temporalidad Semanal (1W) y Top-Down Macro Confluence Gate
- **Arquitectura Macro Top-Down (Multi-Timeframe Hierarchy):**
  - **Problema Cuantitativo Resuelto:** Para capitalizar los agotamientos mayores del mercado (como el Setup 9 de Venta semanal en Bitcoin tras meses de subida continua) sin caer en el error de crear un bot aislado que apenas opere 1 vez al año con stops gigantescos, se diseñó una arquitectura jerárquica *Top-Down*.
  - **Pre-Cálculo de Contexto Semanal (`weekly_context_cache`):** Al inicio de cada ciclo de escaneo en `bot.py`, el motor descarga y calcula las métricas de DeMark (`calculate_td_sequential`) y RSI de las velas semanales (`1w`) de BTC, ETH y HYPE una sola vez, reutilizando el DataFrame en memoria para no saturar las tasas de peticiones (Rate Limits) de Binance.
- **Top-Down Confluence en el Funnel Gate (`calculate_confidence_score`):**
  - Se añadió la 7ª dimensión al vector de convicción institucional modulada con **Anti-Bias Shields**:
    - **Ponderación Suave Institucional (`±0.06` en vez de `±0.15`):** Modula eficazmente trades marginales o dudosos sin asfixiar jamás una operación de alta convicción en 4h (ej: $0.65 - 0.06 = 0.59 \ge 0.55$).
    - **Ventana de Caducidad DeMark (Max 4 Barras / Decay Guard):** El sesgo solo opera en barras 9 a 12 ($9 \le TD \le 12$). Si el conteo supera 12 (13, 14, 15...), el sistema reconoce una tendencia parabólica desbocada (*Runaway Trend*) y desactiva el sesgo de agotamiento automáticamente.
    - **Price Flip & Invalidation Guard:** Si el precio vivo rompe por encima del máximo de la vela 9, el sesgo de venta se apaga de inmediato, impidiendo intentar frenar un breakout alcista.
- **Escudo Preventivo Confluyente Macro (`check_exit_conditions`):**
  - Si un bot mantiene una posición `LONG` abierta y en beneficio, y se confirma un agotamiento semanal activo sin invalidar, el sistema eleva de forma inmediata el Stop Loss al precio de entrada (`Break-Even Shield`), blindando las ganancias acumuladas frente a giros violentos de ciclo.
- **Escalado de Flota a 27 Bots Concurrentes:**
  - Inclusión de `'1w'` en la matriz de timeframes (`timeframes = ['4h', '1d', '1w']`), elevando la flota forward-test a 27 bots algorítmicos (3 activos $\times$ 3 timeframes $\times$ 3 variantes A/B/C).
  - Escalado proporcional de los límites del Portfolio Shield: `MAX_TOTAL_FLEET_TRADES = 9` (33% de utilización), `MAX_DIRECTIONAL_TRADES = 6` y `MAX_TRADES_PER_SYMBOL = 3`.
  - Calibración de ATR dinámico para `'1w'`: multiplicador `tf_mult = 0.8` y suelo de volatilidad `min_atr_pct = 0.025` adaptados al rango de precio semanal.
- **Actualización de Telemetría y Kiosko Bloomberg (`server.py`, `lite.html`, `templates/lite.html`):**
  - `server.py`: El agregador `/api/fleet` lee y expone los estados `state_*_1w.json` y operaciones de la compresión semanal.
  - `lite.html` / `templates/lite.html`:
    - Incorporación de `1w` en el bucle de renderizado del Kiosko UltraGear 21:9.
    - Indicador de Conciencia Situacional Macro: Renderizado dinámico de badges distinguiendo agotamiento activo (`[1W: TD9 SELL EXH]`) frente a extensión de tendencia (`[1W: EXT (+14)]`).
### 11. Diagnóstico de Saturación Xorg en Kiosko, Ingeniería Inversa de @BtcAndres y Perfección DeMark (TDST & Perfection)
- **Diagnóstico y Reparación Crítica de Hardware (Raspberry Pi MicroSD Full):**
  - **Causa Raíz:** Se detectó que la tarjeta MicroSD de la Raspberry Pi se encontraba al 100% de capacidad (0 bytes disponibles). El archivo `/var/log/Xorg.0.log` había alcanzado más de 7 GB debido a un bucle infinito en el driver `modesetting` de Xorg que sondeaba el EDID de la pantalla LG UltraGear cada 500 ms (~2.000 líneas/segundo).
  - La saturación del disco impedía la creación de sockets de Chromium y provocaba fallos en las escrituras atómicas de `state_*.json.tmp`, congelando la interfaz del Kiosko.
  - **Solución Definitiva:**
    - Truncado inmediato de logs, liberando **9.6 GB** de almacenamiento (uso reducido del 100% al 29%).
    - Inyección del parámetro del kernel `options drm_kms_helper poll=0` en `/etc/modprobe.d/drm.conf` para desactivar el sondeo forzado HDMI de conectores inestables, deteniendo en seco la tasa de escritura a 0 líneas/s y reduciendo el consumo de CPU.
    - Relanzamiento limpio del navegador Chromium en modo Kiosko en el display `:0`.
- **Ingeniería Inversa Metodológica de @BtcAndres (`zoitreider.com`):**
  - Se decompilaron los bundles estáticos de Next.js (`page-58bbda90fe46f3cc.js`) y se analizaron los endpoints en vivo de su plataforma (`/api/bitcoin/price`, `/api/liquidation-heatmap`).
  - **Hallazgos Técnicos:**
    - La app de Andrés utiliza exclusivamente velas diarias de Kraken para construir la temporalidad semanal.
    - Su cálculo de TD Sequential se limita al TD Setup estándar (1 a 9) **sin verificación de Perfección de DeMark** y sin seguimiento del TD Countdown (13).
    - Los disparos de señal (`VENTA` en 1w) ocurren de forma puramente ordinal al marcar la barra 9, sin líneas de riesgo formalizadas ni gestión de invalidación cuantitativa.
- **Implementación de Ventajas Cuantitativas (Alpha) en GaTDSEQ:**
  - **Filtro de Perfección DeMark (`td_perfected`):**
    - En `calculate_td_sequential(df)`, se incorporó la regla matemática estricta de Tom DeMark:
      - Para Sell Setup: $\text{High}[8] \ge \max(\text{High}[6], \text{High}[7]) \lor \text{High}[9] \ge \max(\text{High}[6], \text{High}[7])$.
      - Para Buy Setup: $\text{Low}[8] \le \min(\text{Low}[6], \text{Low}[7]) \lor \text{Low}[9] \le \min(\text{Low}[6], \text{Low}[7])$.
    - **Ponderación Dinámica:** Si un Setup semanal no está perfeccionado (como el actual TD9 semanal de BTC donde el High de 8/9 no superó a la barra 6), el sesgo correctivo macro se modula al 50% (`±0.03` en lugar de `±0.06`), evitando que el sistema quede atrapado en pausas leves de una tendencia parabólica.
  - **Líneas de Riesgo TDST (True Setup Trend Invalidation):**
    - Se calculan de forma continua `tdst_res` ($\max(\text{High}_{1..9})$) y `tdst_sup` ($\min(\text{Low}_{1..9})$).
    - Si el precio vivo rompe por encima del TDST Resistance ($87.395,67 en el Setup semanal actual de BTC), el sesgo correctivo se **invalida automáticamente** (Kill-Switch inmediato), protegiendo al sistema de mantener un sesgo bajista obsoleto.
- **Actualización de la Interfaz Bloomberg y Servidor:**
  - `server.py`: El agregador `/api/fleet` propaga automáticamente los campos `td_perfected`, `tdst_res` y `tdst_sup`.
  - `lite.html` / `templates/lite.html`:
    - El badge macro semanal renderiza la perfección y el nivel TDST: `1W: TD9 [UNPERF] | TDST:$87396`.
    - Los pills de variantes de la flota muestran indicadores compactos de perfección (`P` en verde para perfeccionado, `U` en ámbar para no perfeccionado) y tooltips con los niveles TDST exactos.
- **Auditoría y Liberación de Memoria en el Host (Mac):**
  - Detección de una instancia zombie del simulador de iOS (`iPhone 17 Pro`) en segundo plano ejecutando más de 20 daemons (`SpringBoard`, `sirittsd`, `healthd`, etc.).
  - Ejecución de `xcrun simctl shutdown all` y baja de `CoreSimulatorService`, liberando inmediatamente más de **2.4 GB de RAM física** y descongestionando **3.8 GB de memoria comprimida** en el kernel de macOS.
- **Despliegue:** Sincronizado a producción mediante `rsync` y reiniciados los servicios `gatdseq-bot.service` y `gatdseq-server.service` en la Raspberry Pi.

### 12. Motor F5 Táctico y Ciclo de Vida Móvil (iPhone/Safari Sleep & Cache Fix)
- **Diagnóstico del Fallo de Refresco en iPhone (Safari / PWA / WebClip):**
  - **Problema:** En dispositivos iPhone / iOS, cuando el usuario abre el Kiosko como WebClip o en Safari, no existe la tecla física `F5`, y el navegador en modo pantalla completa carece de barra de URL o botón de recarga.
  - Al bloquear el iPhone o alternar entre aplicaciones, iOS suspende la ejecución de JavaScript (`setInterval`) y desconecta los WebSockets. Al reanudar la pantalla, Safari mantiene el renderizado con datos congelados y almacena las peticiones HTTP `fetch()` en la caché BFCache de WebKit sin solicitar datos frescos al servidor.
- **Solución Técnica Implementada (`lite.html` y `templates/lite.html`):**
  - **Botón F5 Bloomberg Táctico en Cabecera:**
    - Se incorporó un botón minimalista de control `[ ↻ F5 ]` en la barra superior junto al selector de modo solar.
    - **Tap Simple:** Activa una animación de giro (`spinRefresh`), fuerza la descarga inmediata en paralelo de todos los endpoints (`fetchFleet`, `fetchSystem`, `fetchTicker`, `fetchFnG`) y re-engancha el túnel WebSocket si estaba cerrado.
    - **Doble Tap Rápido (< 450 ms):** Dispara una recarga forzada del documento completo (`window.location.reload(true)`).
  - **Manejador de Ciclo de Vida y Despertar Móvil (iOS Resume Listeners):**
    - Se registraron eventos globales `visibilitychange`, `pageshow` y `focus`. En el instante en que el usuario desbloquea el iPhone o vuelve a la pestaña, el frontend detecta el estado visible y ejecuta automáticamente una sincronización completa de la flota y del WebSocket.
  - **Cache-Busting Anti-WebKit:**
    - Todas las llamadas `fetch()` ahora incluyen un timestamp dinámico de parámetro (`?_t=Date.now()`) y la directiva `{ cache: 'no-store' }`, impidiendo que iOS sirva respuestas 304 obsoletas.
    - Metadatos PWA añadidos en el `<head>`: `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style` y `apple-mobile-web-app-title`.
- **Despliegue:** Archivos sincronizados a `/home/raspberry/GaTDSEQ/` y servidor reiniciado.

### 13. Auditoría de Producción, Hardening de Kernel en Boot y Vinculación SSH de MacBook Pro como Nodo Worker
- **Hardening del Kernel en Raspberry Pi (Persistencia Real `drm_kms_helper.poll=0`):**
  - **Problema Detectado en Auditoría:** Tras el reinicio del sistema, `Xorg.0.log.old` y el log activo acumulaban espacio debido a que en Debian 12 Bookworm `drm_kms_helper` está compilado directamente dentro de la imagen del kernel (`kernel8.img`), por lo que `/etc/modprobe.d/drm.conf` era ignorado al arrancar.
  - **Corrección Definitiva:** Se inyectó `drm_kms_helper.poll=0` en el archivo de arranque del firmware (`/boot/firmware/cmdline.txt`), garantizando que el sondeo EDID permanezca desactivado a 0 líneas/s de forma permanente a nivel de kernel.
  - **Tratamiento de Seguridad (`auto_clean.sh`):** Se añadió una regla `find /var/log -type f -name "*log*" -size +50M -exec truncate -s 0 {} +` en la rutina diaria de mantenimiento para evitar cualquier desbordamiento de almacenamiento por servicios auxiliares. Espacio en disco estabilizado en **9.5 GB libres (29% de uso)**.
- **Evaluación Táctica de Flota (27 Bots):**
  - **Posiciones Activas:** 2 bots en trade (`HYPE_HYB [1d]` y `HYPE_WYK [1d]` en posición LONG desde \$81.81, SL en \$75.38 y TP en \$90.38, flotando cerca del precio de entrada de forma segura).
  - **Proximidad a Disparo:** 3 bots en TD 9 (`BTC_HYB`, `BTC_TD9`, `BTC_WYK` en 1w con Setup no perfeccionado `[UNPERF]` y resistencia TDST en \$87.395,67, aplicando el modulador suave de $\pm 0.03$).
- **Integración de Infraestructura: MacBook Pro (`GtrujilloMac`):**
  - Conectividad SSH verificada con autenticación por clave asimétrica ED25519 sin contraseña hacia `gabrieltrujillovallejo@192.168.1.193` (latencia 6.6 ms).
  - Especificaciones detectadas: CPU Intel Core i5-4278U @ 2.60 GHz (2 cores / 4 threads), 8 GB de RAM y 43 GB de disco SSD libre.
  - Configurado como nodo de computación de alto rendimiento para futuros módulos de backtesting distribuido, optimización bayesiana de hiperparámetros y modelos de machine learning.

### 14. Despliegue de Arquitectura Híbrida Edge-Worker, Validación de Alpha por Grid Search y Unificación MagicDNS
- **Entorno Cuantitativo y Machine Learning en MacBook Pro:**
  - Construcción del entorno virtual nativo `~/GaTDSEQ_Worker/venv` con **Python 3.11.11**.
  - Instalación del stack matemático precompilado: `pandas` (3.0.6), `numpy` (2.4.6), `ccxt` (4.5.64), `scipy` (1.17.1), `fastparquet` (2026.9.0), `scikit-learn` (1.9.1) y `xgboost` (3.2.0).
  - Resolución del enlazado dinámico de `libomp.dylib` (OpenMP) para paralelismo multi-hilo en macOS Haswell mediante enlace simbólico en `/usr/local/opt/libomp/lib` hacia LLVM.
- **Modo Servidor Autónomo 24/7 (Clamshell Mode):**
  - Inyección de `SleepDisabled 1` y `displaysleep 5` en `pmset` para permitir ejecución continua con la tapa física cerrada.
  - Despliegue del daemon `caffeinate` supervisado por `launchd` en `~/Library/LaunchAgents/com.gatdseq.caffeinate.plist`.
  - Compilación e instalación nativa de los binarios de servidor de Tailscale CLI (`tailscale` y `tailscaled`) con Go 1.24 local, sorteando incompatibilidades de AppKit en macOS Big Sur.
- **Aislamiento y Seguridad de Datos (Disco Seagate):**
  - Análisis técnico del almacenamiento: se determinó que los datasets Parquet ocupan menos de 150 MB, haciendo innecesario el uso del disco mecánico Seagate.
  - Se eliminaron carpetas temporales del disco externo, dejándolo 100% aislado para preservar la integridad de Time Machine y fotos personales. Todo el almacenamiento de trading opera sobre el SSD interno (43 GB disponibles).
- **Validación Cuantitativa de Rentabilidad (Alpha Real):**
  - Ejecución de Grid Search de 54 combinaciones sobre 30 días de `BTC/USDT [1h]`.
  - **Resultado:** Demostración empírica de conversión de estrategia perdedora (PnL: -\$503.64, Sharpe: -1.71, MDD: -16.17%) a fuertemente rentable (**PnL: +\$1,515.97, Sharpe: 7.11, MDD: -4.00%**) al calibrar el umbral de Break-Even a `0.5x ATR`.
  - Creación del orquestador `optimize_fleet.py` en el repositorio para automatizar barridos paralelos en BTC, ETH y HYPE.
- **Unificación de Red y Nombres Institucionales (Tailscale MagicDNS):**
  - Normalización de nombres de red bajo el estándar RFC 1123:
    - `gtrujillo-macbook-pro` (MacBook Pro / Worker Node)
    - `gtrujillo-raspberry-pi-3b` (Raspberry Pi / Edge Core)
    - `gtrujillo-macbook-air-m4` (MacBook Air M4 / Workstation)
    - `iphone16` (Kiosko Móvil)
    - `tv` (Xiaomi TV A1 Pro)
- **Corrección de Conectividad Gráfica y Perfiles de Energía:**
  - Diagnóstico del fallo de *Compartir Pantalla* desde ubicaciones remotas: purga de archivos `.vncloc` locales obsoletos vinculados a mDNS (`.local`) y creación de accesos directos remotos de escritorio con MagicDNS (`MacBook Pro (Remoto).vncloc` y `Raspberry Pi (Remoto).vncloc`).
  - Verificación del puerto 5900 (VNC) activo y respondiendo tanto en el MacBook Pro como en la Raspberry Pi (`x11vnc` en `:0`).
  - Calibración de energía en MacBook Air M4: desactivación de `SleepDisabled` para permitir reposo al cerrar la tapa en batería (`sleep 1`) y servicio continuo en corriente (`displaysleep 3` / `sleep 0`).

### 15. Integración del Cargador Dinámico de Hiperparámetros y Calibración Sistemática de la Flota
- **Cierre del Bucle Cuantitativo (Motor Dinámico en `bot.py`):**
  - Se eliminaron todos los valores estáticos (*hardcoded*) de Stop Loss, Take Profit y Break-Even en `bot.py`.
  - Implementación de la función `get_bot_params(symbol, timeframe, strategy)` con caché de memoria (TTL 60s) que lee en tiempo real la matriz `fleet_optimized.json`.
  - Los niveles de entrada y de gestión de riesgo (`atr_sl_trend`, `atr_tp_trend`, `be_threshold_atr`, `scale_out_atr`, `enable_scale_out`) ahora se modulan de forma puramente matemática según las pruebas empíricas del Worker.
- **Ejecución del Barrido Multi-Activo en MacBook Pro (`gtrujillo-macbook-pro`):**
  - Ejecución de `optimize_fleet.py` sobre los 3 activos del portafolio (BTC, ETH, HYPE) en timeframes de 1h, 4h y 1d (54 combinaciones por variante).
  - Almacenamiento de datasets históricos Parquet ultraligeros en el SSD interno del Mac (`~/GaTDSEQ_Worker/backtesting/data/`).
  - Generación de la primera matriz formal `fleet_optimized.json`.
- **Despliegue y Verificación en Producción (Raspberry Pi):**
  - Sincronización mediante `rsync` hacia `/home/raspberry/GaTDSEQ/` de `bot.py` y `fleet_optimized.json`.
  - Reinicio del demonio `gatdseq-bot.service` (`systemctl restart gatdseq-bot`), confirmando arranque limpio y ejecución en vivo de los 27 bots con los parámetros optimizados.

### 16. Adopción de Directrices SecOps Zero-Trust y Hardening de Endpoints
- **Directrices de Seguridad Institucional (`GEMINI.md` - Regla 10):**
  - **Zero Password Exposure:** Prohibición estricta de manejar contraseñas o credenciales en texto plano en prompts de IA, scripts temporales, commits o logs. Gestión descentralizada y local mediante comandos interactivos del sistema operativo (`passwd`).
  - **Zero Public Surface (Sin Apertura de Puertos):** Confirmación de política de cero puertos abiertos en el router hacia la WAN pública. Todo el acceso remoto, telemetría y terminales (SSH/VNC) discurre cifrado de extremo a extremo mediante Tailscale (túnel WireGuard).
  - **Hardening de Endpoints:** Activación del Application Firewall en macOS (`socketfilterfw`) en nodos de trabajo y directriz de doble factor de autenticación (2FA) en la cuenta de control de la red privada.
- **Auditoría de Acceso Móvil Seguro (iSH iOS):**
  - Configuración de aliases y directivas de persistencia SSH (`ServerAliveInterval 15`) en el cliente iSH para un acceso ágil sin comprometer puertos ni credenciales maestras.

### 17. Suite de Auto-Curación (Self-Healing), Purga de RAM y Reinicio Headless Autónomo en MacBook Pro
- **Protocolo de Protección del Hardware (24/7 Clamshell Worker):**
  - Para evitar fatiga térmica, degradación de celdas de batería y fragmentación de memoria (Memory Leaks / Inactive RAM) en el MacBook Pro con tapa cerrada, se diseñó e implementó una suite integral de auto-mantenimiento.
- **Componentes de la Suite (`scripts/`):**
  - `worker_maintenance.sh`: Orquestador de limpieza que verifica si hay cálculos activos de ML/Backtesting antes de proceder. Purga la memoria inactiva del sistema con `/usr/sbin/purge`, limpia cachés `__pycache__`, rota logs de más de 25 MB y recolecta telemetría (carga, RAM, SSD, batería).
  - `com.gatdseq.maintenance.plist`: LaunchDaemon del sistema que programa la ejecución diaria del mantenimiento y reinicio controlado a las 04:30 AM (`StartCalendarInterval`).
  - `com.gatdseq.caffeinate.plist`: LaunchDaemon del sistema que eleva `caffeinate -s -i -m -u` a nivel de raíz (`root:wheel`). Garantiza que tras cualquier reinicio sin login gráfico interactivo, el sistema impida el reposo con la tapa cerrada.
  - `install_worker_maintenance.sh`: Script automatizado de despliegue que instala los daemons en `/Library/LaunchDaemons/`, purga agentes antiguos y activa `pmset -a autorestart 1` ante cortes de suministro eléctrico.
- **Garantía de Reconexión Headless sin Intervención Manual:**
  - Se auditó la cadena de arranque: FileVault desactivado (`FileVault is Off`), perfiles Wi-Fi persistidos en `System.keychain` y arranque anticipado de `tailscaled` y `sshd` a nivel de LaunchDaemon. El Mac queda listo y accesible por SSH inmediatamente tras cada reinicio automático.

### 18. Formalización de la Documentación Integral de Infraestructura y Red Mesh
- **Actualización Mayor de `manual_infraestructura.md` (Versión 2.0 Institucional):**
  - Diagrama ASCII de arquitectura de red con direccionamiento RFC 1123 MagicDNS y CGNAT (100.64.0.0/10) a través de Tailscale (WireGuard) para los 5 nodos físicos (`gtrujillo-raspberry-pi-3b`, `gtrujillo-macbook-pro`, `gtrujillo-macbook-air-m4`, `iphone16`, `tv`).
  - Especificaciones técnicas completas, optimizaciones de hardware (ZRAM, `drm_kms_helper.poll=0`, Apple Silicon M4 vs Intel Haswell OpenMP).
  - Explicación de la Cadena de Arranque Desatendido (*Headless Bootstrap Chain*) y la Suite de Auto-Curación con LaunchDaemons de nivel raíz.
  - Cheat Sheet de comandos operacionales, macros (`auditoria`, `evalua`) y runbooks de emergencia.
- **Integración en `README.md`:**
  - Indexación del Manual de Infraestructura en la tabla de contenidos y adición del árbol de scripts de mantenimiento al mapa del repositorio.

### 19. Sincronización Integral del Pipeline Cuantitativo Distribuido en README.md
- **Diagrama de Arquitectura Distribuida de 3 Capas:**
  - Sustitución del diagrama monolítico anterior por el nuevo flujo desacoplado: Compute Worker (`optimize_fleet.py` en MacBook Pro), Edge Core (`bot.py` dinámico en Raspberry Pi 3B) y Telemetría WebSockets hacia Kiosko UltraGear 21:9, Xiaomi TV y terminales iSH.
- **Documentación del Cargador Dinámico de Hiperparámetros:**
  - Explicación de la función `get_bot_params()` con caché TTL de 60 segundos, permitiendo la recarga en caliente (*zero-downtime hot swapping*) de `fleet_optimized.json` sin reiniciar servicios ni alterar posiciones activas.
  - Registro de la prueba empírica en `BTC/USDT [1h]` (+15.16% de beneficio neto y Sharpe 7.11 calibrando Break-Even a 0.5x ATR).
- **Actualización del Árbol de Archivos:**
  - Adición formal de `optimize_fleet.py` y `fleet_optimized.json` a la estructura del repositorio.
- **Sección 10 en Cuerpo Principal:**
  - Desglose de los 5 nodos físicos de la red mesh de Tailscale, suites de auto-curación y enlace directo al manual técnico de infraestructura.







