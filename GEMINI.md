# REGLAS DEL PROYECTO (Modo de Proceder Constante)

Como asistente de Inteligencia Artificial para el desarrollo de GaTDSEQ, DEBES cumplir siempre las siguientes reglas:

### 1. Diario de Desarrollo Obligatorio
Antes de ejecutar CUALQUIER comando `git push`, DEBES actualizar obligatoriamente el archivo `DIARIO_DE_DESARROLLO.md` añadiendo un resumen técnico, claro y profesional de las modificaciones o funciones nuevas que se han integrado.

### 2. Mantenimiento y Limpieza del Repositorio
- Borra siempre tus scripts de parcheo temporales (como `patch_*.py`) antes de hacer commit.
- **Prohibido** subir archivos dinámicos de estado (`state_*.json`, `trades_*.json`, `bot_unified.log`) al repositorio remoto. Estos archivos pertenecen únicamente a la Raspberry Pi. Mantén el `.gitignore` actualizado.

### 3. Idioma y Tono Institucional (Bloomberg Aesthetic)
- **Front-End / UI:** Todo el texto visible para el usuario (Kiosko) debe estar en inglés financiero profesional (Holdings, Unrealized PNL, Risk Exp., etc).
- **Diseño:** Mantén siempre y sin excepciones la estética "Terminal Bloomberg": tipografía monospace (Courier New), cero bordes redondeados, fondo negro puro, y la paleta estricta Ámbar/Cian/Verde/Rojo.

### 4. Optimización de Hardware (Raspberry Pi Edge Device)
- Ten en cuenta en todo momento que el backend en Python corre en una máquina con recursos muy limitados.
- Trata de descargar todo el trabajo matemático derivado de la visualización al Front-End (JavaScript) del dispositivo cliente para mantener la CPU y RAM del servidor al mínimo.
- Las variables de Python y los bucles masivos (como Pandas/CCXT) deben ser optimizados (usar siempre `gc.collect()` si es necesario para evitar Memory Leaks).

### 5. Control de Versiones
- Usa *Conventional Commits* en el repositorio (`feat:`, `fix:`, `docs:`, `refactor:`).
- Realiza siempre las subidas a producción a la Raspberry mediante `rsync` y aplica reinicios por `systemctl` cuando toques Python.

### 6. Gestión de Procesos en Segundo Plano
- **Prohibido dejar procesos SSH o tareas de monitoreo (`tail -f`, etc.) abiertos en segundo plano.** Tras inspeccionar logs o realizar diagnósticos, SIEMPRE debes matar o detener esos procesos antes de finalizar tu intervención para no dejar conexiones zombis drenando recursos.
