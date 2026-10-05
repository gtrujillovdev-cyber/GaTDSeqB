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
