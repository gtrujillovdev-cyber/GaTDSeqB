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
