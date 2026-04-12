# Proyecto Teyka — Documentación Técnica Completa

> **Gestión del Estado Nervioso**  
> De la biometría pasiva a la intervención proactiva.  
> Impacthon 2026 — USC

---

## 1. Visión General

El Proyecto Teyka propone un cambio de paradigma: pasar del **bloqueo reactivo de aplicaciones** a la **gestión proactiva del estado nervioso**. Utilizamos la biometría como "alarma temprana" de la pérdida de autorregulación cognitiva.

El sistema calcula un **Índice de Saturación (IS)** en tiempo real que combina estrés fisiológico (variabilidad cardíaca) con patrones de comportamiento digital (uso de pantalla, actividad física). Cuando el IS supera el **umbral crítico del 70%** y el usuario se halla en un estado cognitivo **de inercia u Ocio**, el sistema genera una **intervención proactiva context-aware (Nudge)** sugiriendo medidas correctoras estructuradas a través del asistente de Inteligencia Artificial.
### Referencia Académica

> Wang, R., Chen, F., Chen, Z. et al. «StudentLife: Assessing Mental Health, Academic Performance and Behavioral Trends of College Students using Smartphones», ACM UbiComp, 2021.

---

## 2. Arquitectura del Producto

El proyecto se divide en **tres productos** independientes:

```
Impacthon/
├── Teyka/                   ← Dashboard de presentación + Panel Admin
│   ├── index.html         ← Dashboard público (pitch Impacthon)
│   ├── admin.html         ← Panel de investigación y data mining
│   ├── extract_gem.py     ← ETL pipeline (IS diario + sesiones)
│   └── gem_data.json      ← Datos procesados
│
├── Teyka - phone/           ← App Móvil de Salud (usuario final)
│   ├── mobile.html        ← App iOS-style con IS intradía
│   ├── mobile.css/js      ← Frontend móvil completo
│   ├── extract_gem.py     ← ETL pipeline v4 (IS horario)
│   └── gem_data.json      ← Datos con resolución horaria
│
└── dataset_final_pitch.csv   ← Fitbit RMSSD data
```

### Productos

| Producto | Público | Descripción |
|---|---|---|
| **Dashboard Pitch** (`Teyka/index.html`) | Jurado / público | Dashboard visual para la presentación del Impacthon. Hero, IS Live, gráficos, simulador de nudge |
| **Admin Panel** (`Teyka/admin.html`) | Investigadores | Panel con observabilidad, datos agregados, correlaciones, logs de alertas, banco de pruebas, exportación CSV/JSON |
| **App Móvil** (`Teyka - phone/mobile.html`) | Usuario final | App de salud estilo iOS con gráfico intradía Trade Republic, notificaciones push, historial calendárico |

---

## 3. Datasets Utilizados

### 3.1 Fitbit — Fitabase (Kaggle)

- **Fuente:** [Fitbit Fitness Tracker Data](https://www.kaggle.com/arashnic/fitbit) via Fitabase
- **Registros:** 2.4 millones de mediciones de frecuencia cardíaca segundo a segundo
- **Participantes:** 14 usuarios
- **Variables extraídas:**
  - **RMSSD (ms):** Root Mean Square of Successive Differences — métrica gold-standard de la Variabilidad de la Frecuencia Cardíaca (HRV). Calculada a partir de los Inter-Beat Intervals (IBI) derivados de `heartrate_seconds`.
  - **SedentaryMinutes:** Minutos de sedentarismo registrados por Fitbit (acelerómetro).
  - **Perfil de Riesgo:** Clasificación derivada del RMSSD (Alto/Medio/Bajo).
- **Uso en el sistema:** Establece la **baseline poblacional de RMSSD** (21.58 ms) y proporciona los datos de referencia para calibrar los umbrales de estrés fisiológico.

### 3.2 GLOBEM — UW EXP Lab

- **Fuente:** [GLOBEM Dataset](https://github.com/UW-EXP/GLOBEM) — University of Washington
- **Participantes:** 40 usuarios (4 cohortes, `INS-W-sample_1` a `INS-W-sample_4`)
- **Período:** Multi-anual (2018-2019)
- **Archivos utilizados:**
  - `FeatureData/screen.csv` — Datos de uso de pantalla procesados por RAPIDS
  - `FeatureData/steps.csv` — Datos de pasos y actividad procesados por RAPIDS

#### Variables de Screen (por segmento: morning/afternoon/evening/night/allday)

| Variable RAPIDS | Descripción | Uso en Teyka |
|---|---|---|
| `sumdurationunlock` | Suma total de tiempo con pantalla desbloqueada (min) | **screen_min** — Tiempo total de pantalla |
| `countepisodeunlock` | Número de veces que se desbloqueó el teléfono | **unlocks** — Frecuencia de uso |
| `avgdurationunlock` | Duración media de cada sesión de desbloqueo (min) | **avg_session** — Detección de sesiones largas |
| `maxdurationunlock` | Duración máxima de una sola sesión (min) | **max_session** — Detección de sesiones dominantes |
| `mindurationunlock` | Duración mínima de sesión (min) | Contexto |
| `stddurationunlock` | Desviación estándar de duración de sesiones (min) | Variabilidad de patrones |

#### Variables de Steps (por segmento)

| Variable RAPIDS | Descripción | Uso en Teyka |
|---|---|---|
| `sumsteps` | Suma total de pasos | **steps** — Nivel de actividad física |
| `sumdurationsedentarybout` | Duración total de bouts sedentarios (min) |  Ver corrección abajo |
| `sumdurationactivebout` | Duración total de bouts activos (min) | **active_min** — Tiempo realmente activo |

####  Corrección del Sedentarismo

El campo `sumdurationsedentarybout` de RAPIDS **NO mide sedentarismo real**. RAPIDS lo calcula como:

```
sedentary_bout = tiempo_total_segmento - active_bout
```

Cada segmento tiene ~360 min (6 horas), por lo que el `allday` reporta ~1200-1400 min (20-23h), incluyendo **sueño e inactividad total**. Esto NO es sedentarismo en el sentido clínico.

**Corrección aplicada en Teyka:**
```python
real_sedentary = 960 - active_min_allday  # 960 = 16 horas despierto
```

Esto da valores realistas de 600-860 min de sedentarismo diurno, que es el complemento del tiempo realmente activo durante las horas de vigilia.

#### Segmentos Temporales

| Segmento | Horas | Duración |
|---|---|---|
|  Morning | 06:00 — 12:00 | 6 horas |
|  Afternoon | 12:00 — 18:00 | 6 horas |
|  Evening | 18:00 — 00:00 | 6 horas |
|  Night | 00:00 — 06:00 | 6 horas |

---

## 4. Pipeline ETL (`extract_gem.py`)

Existen **dos versiones** del ETL pipeline, una para cada producto:

### 4.1 ETL v4 Hybrid — Dashboard + Admin (`Teyka/extract_gem.py`)

Genera datos con resolución **diaria**. Usa sigmoide logística sobre CD para BehaviorScore + StressScore lineal.

```
Fitbit (dataset_final_pitch.csv / cache json)
    ├── RMSSD por usuario (baseline poblacional: 21.58 ms)
    └── Fallback: carga desde gem_data.json si CSV no disponible

GLOBEM (4 cohortes × screen.csv + steps.csv)
    ├── Merge por (pid, date)
    ├── Renombrado de columnas RAPIDS → nombres legibles
    └── Filtrado: dropna en screen_min_allday y steps_allday
```

**Output:** `gem_data.json` con estructura:
```json
{
  "engine": "Hybrid v4 (CD sigmoid + linear stress)",
  "hyperparameters": { "alpha": 1.0, "beta": 3.0, "gamma_cd": 0.03, ... },
  "fitbit_baseline_rmssd": 21.58,
  "fitbit_users": [...],
  "globem_users": [
    {
      "pid": "INS-W_617",
      "avg_IS": 62.7,
      "daily": [
        {
          "date": "2020-04-28",
          "IS": 65.3,
          "stress_score": 54.2,
          "behavior_score": 78.5,
          "CD": 523.1,
          "B_base": 0.943,
          "session_class": { "morning": "productive", ... }
        }
      ]
    }
  ]
}
```

### 4.2 ETL v4 — App Móvil (`Teyka - phone/extract_gem.py`)

Genera datos con resolución **horaria** (24 data points por día) para el gráfico intradía.

**Output:** `gem_data.json` con estructura:
```json
{
  "users": [
    {
      "id": "Usuario 1",
      "days": [
        {
          "date": "2020-04-28",
          "daily_is": 62.3,
          "hourly": [
            { "hour": 0, "is": 12.5, "screen": 2.1, "steps": 0, "rmssd": 28.3, "stress": 8.1, "behavior": 5.2 },
            ...
          ],
          "rest_points": [9, 14, 20]
        }
      ],
      "weekly": [...]
    }
  ]
}
```

### 4.3 Cálculo de Baselines por Usuario

```python
# Ratio de actividad: qué fracción de las 16h despierto es activa
activity_ratio = active_min_allday / 960  # rango 0 a ~0.7

# RMSSD baseline: más actividad → mejor tono vagal → baseline más alta
synth_rmssd_baseline = 20 + activity_ratio * 20  # rango 20-34 ms
```

**Justificación clínica:** El RMSSD mide tono vagal (activación parasimpática). La evidencia muestra que el sedentarismo crónico reduce el tono vagal basal — el nervio vago pierde capacidad de regulación. Esto se traduce en menor resiliencia al estrés agudo.

### 4.4 Selección de Usuarios Diversos

Se seleccionan **8 usuarios** representativos con perfiles extremos y medios:
- 2 con **más pantalla** (>600 min/día)
- 2 con **menos pantalla** (<130 min/día)
- 2 con **más pasos** (>19k pasos/día)
- 2 con **más sedentarismo** corregido
- Relleno hasta 8 con usuarios intermedios

---

## 5. Índice de Saturación (IS)

### 5.1 Fórmula

```
IS = 0.55 × StressScore + 0.45 × BehaviorScore
```

El IS combina dos dimensiones independientes:
- **StressScore (55%):** Estado fisiológico del sistema nervioso autónomo (lineal)
- **BehaviorScore (45%):** Patrón de comportamiento digital (**sigmoide logística** sobre Carga Digital compuesta)

### 5.2 StressScore — Componente Fisiológico (Lineal)

El StressScore mide cuánto ha caído el RMSSD diario respecto a la baseline del usuario.

```python
# 1. Normalizar inputs
screen_norm = min(screen / 600, 1)          # Satura a 10 horas
sed_norm = min(real_sedentary / 900, 1)     # Satura a 15h de sedentarismo diurno

# 2. Protección por actividad: capped al 40%
activity_protection = min(steps / 12000, 1) * 0.40

# 3. Caída del RMSSD
rmssd_drop = (screen_norm × 0.6 + sed_norm × 0.4) × 12 × (1 - activity_protection)
daily_rmssd = max(baseline - rmssd_drop, 8)  # Floor: 8 ms

# 4. Score = desviación porcentual
stress_score = ((baseline - daily_rmssd) / baseline) × 100
```

| Factor | Peso en la caída | Justificación |
|---|---|---|
| Pantalla | 60% | Estímulo principal de hiperfocalización y activación simpática |
| Sedentarismo | 40% | Reduce activación parasimpática por inmovilidad prolongada |
| Pasos (protección) | Hasta -40% | La actividad física favorece la regulación vagal |

### 5.3 BehaviorScore — Componente Conductual (Sigmoide CD)

El BehaviorScore utiliza una **sigmoide logística** sobre la Carga Digital compuesta (CD), reemplazando la normalización lineal para capturar la relación dosis-respuesta real de toxicidad digital.

#### 5.3.1 Carga Digital Compuesta (CD)

```python
CD = α × S_dur + β × U_freq - γ × P_acc
```

| Variable | Mapeo GLOBEM | Coeficiente | Justificación |
|---|---|---|---|
| S_dur | `sumdurationunlock` (min) | α = 1.0 | Duración total de pantalla |
| U_freq | `countepisodeunlock` | β = 3.0 | Cada desbloqueo ≈ 3 min de carga cognitiva |
| P_acc | `sumsteps` | γ = 0.03 | Compensación por actividad física |

#### 5.3.2 Sigmoide Logística

```python
B_base = 1 / (1 + e^(-k × (CD - θ)))
```
- **k = 0.012** — pendiente de la curva (velocidad de transición)
- **θ = 280** — punto de inflexión (~4.5h pantalla con uso moderado)

**Ejemplos de calibración:**
| Perfil | S_dur | U_freq | Pasos | CD | B_base |
|---|---|---|---|---|---|
| Saludable | 100 min | 20 | 15,000 | -190 | 0.003 |
| Moderado | 400 min | 80 | 8,000 | 400 | 0.81 |
| Problemático | 600 min | 100 | 2,000 | 840 | 0.998 |

#### 5.3.3 Score Final con Penalizaciones

```python
# Entertainment penalty (15 pts per segment)
ent_penalty = ent_count × 15             # 0 a 60

# Night penalty (pantalla nocturna >30 min)
night_penalty = min(night_screen / 60, 1) × 10  # 0 a 10

# Score final
behavior_score = min(B_base × 65 + ent_penalty + night_penalty, 100)
```

### 5.4 Garantías de Consistencia

```python
if ent_count >= 2: IS = max(IS, 50)
if ent_count >= 3: IS = max(IS, 65)
if ent_count >= 3 and screen > p75: IS = max(IS, 75)
if ent_count == 4: IS = max(IS, 78)
if screen > 500 and steps < 3000: IS = max(IS, 75)
```

### 5.5 IS Horario (App Móvil)

En la versión intradía (`Teyka - phone/extract_gem.py`), el IS se calcula **por hora** con mayor sensibilidad:

```python
# Umbrales horarios (más sensibles que diarios)
screen_norm = min(h_screen / 25, 1)       # 25 min/hr saturates
sed_norm = min(h_sedentary / 50, 1)       # 50 min/hr sedentary

# Multiplicador más alto para resolución horaria
rmssd_drop = (screen_norm * 0.6 + sed_norm * 0.4) * 14 * (1 - act_prot)
h_rmssd = max(baseline - rmssd_drop, 6)   # Floor: 6 ms (más bajo)
```

**Puntos Críticos (Rest Points):** Se analizan de forma granular las horas intradía donde la gráfica cruza un porcentaje altísimo y riesgoso de estrés.

### 5.6 Umbral de Alerta y Prevención (Condición Dual 70)

Para evitar falsos positivos por "estrés funcional o bueno" (ej: alta atención continua en un examen importante o trabajando frente al ordenador), la alerta no se dispara únicamente por alcanzar un pico. La notificación y las franjas de riesgo toxicológico visual **sólo se activan si se cumplen DOS condiciones concurrentes**:

1. **Saturación Crítica:** El IS supera el **trigger analítico del 70%** (indicado visualmente por la *threshold line* roja punteada constante en el App Móvil).
2. **Contexto de Ocio (Inercial):** El estado inferido de la sesión recae estrictamente en **"No Productivo"** (Ocio/Entretenimiento pasivo).

Si el IS supera el 70% bajo un foco Productivo, el sistema lo catalogará como "estrés normal/enfocado" asumiéndolo temporal, suprimiendo la alerta para salvar el momentum del usuario.

---

## 6. Clasificación de Sesiones: Productivo vs. Entretenimiento

### 6.1 Principio

No tenemos datos de qué aplicación usa cada persona. La clasificación se basa en el **patrón de uso del móvil** cruzado con la **actividad física** en cada segmento del día. Es una **inferencia conductual**.

### 6.2 Umbrales Personalizados (Per-User Percentiles)

Para cada usuario se calculan umbrales relativos a su propio historial:

```python
# Para cada segmento (morning, afternoon, evening, night):
screen_p50 = percentil 50 del tiempo de pantalla del usuario en ese segmento
screen_p75 = percentil 75
steps_p25  = percentil 25 de pasos del usuario en ese segmento
```

### 6.3 Reglas de Clasificación

####  Productivo
Un segmento se clasifica como **productivo** cuando:
- El tiempo de pantalla está **por debajo de la mediana** del usuario para ese segmento
- **O** los pasos están **por encima del percentil 25** del usuario
- **O** hay muchos desbloqueos con sesiones cortas (patrón de "check-and-go")

####  Entretenimiento
Un segmento se clasifica como **entretenimiento** cuando se cumplen **dos condiciones simultáneas**:

1. **Pantalla por encima de la mediana** del usuario para ese segmento
2. **Y al menos una** señal de absorción pasiva:
   - **Pasos bajos** (< percentil 25) → sentado/tumbado
   - **Patrón binge:** ≤5 desbloqueos con sesión media >15 min
   - **Sesión dominante:** una sesión >30 min que ocupa >60% del tiempo total

####  None
Si el tiempo de pantalla en ese segmento es <3 minutos → dato insuficiente.

---

## 7. Rol del Sedentarismo en el Estrés

El sedentarismo impacta el estrés a través de **dos mecanismos**:

### 7.1 Baseline RMSSD (Efecto Crónico)
Un usuario con más sedentarismo medio tiene un RMSSD basal más bajo (peor tono vagal).

```
Mismo uso de pantalla (400 min):
  - Usuario sedentario (baseline 21 ms): StressScore ≈ 35%
  - Usuario activo (baseline 27 ms): StressScore ≈ 28%
```

### 7.2 sed_norm Diario (Efecto Agudo)
El sedentarismo del día (corregido: 960 - active_min) contribuye al 40% de la caída del RMSSD.

---

## 8. Sistema de Nudge Context-Aware (Gemini Integration)

### 8.1 Disparador Dual (Dual-Condition Trigger)
Siguiendo la prevención de falsos positivos, la intervención preventiva requiere inequívocamente: **(IS > 70% AND app_type == 'non-productive')**.

### 8.2 Flujo Operativo AI (Generative AI Integration)

La app incorpora **Teyka AI**, un motor de intervención impulsado por **Google Gemini 1.5 Flash** (vía Vertex AI / REST API) embebido en el frontend. El pipeline operativo es:

```
1.  Monitoreo Pasivo
   → Smartwatch captura RMSSD, móvil registra pantalla y uso.

2.  Evaluación Dual (Stress + Context)
   → Si el Índice de Saturación (IS) supera el 70% bajo un foco inercial de Ocio, se activa la capa de inferencia.

3.  Generación Semántica (Teyka AI)
   → El cliente web monta un 'System Prompt' al milisegundo fusionando el IS actual + las Aficiones (Hobbies) guardadas del usuario en LocalStorage (incluyendo las creadas a mano).
   → Inyecta a la API de lenguaje: "Escribe una orden de 8 palabras, amable y directa, sobre cómo usar [este hobby específico] para relajar su estrés ahora mismo".
   → La API sintetiza texto y la UI oscurece el fondo mientras "calcula el nudge".

4.  Tolerancia a Fallos (Graceful Degradation)
   → Dado el entorno volátil de hackathon, si las *API Keys* se agotan o el servidor de Google rechaza la llamada, la función en JS atrapa el `catch()` y recurre silenciosamente a un diccionario de plantillas de Fallback (Offline Mode). El usuario siempre recibe su intervención biométrica estructurada al instante.
```

### 8.3 Inyección Estocástica de Datos (Visual Demo)
Para que las pruebas, el jurado, y los simulacros de App sean creíbles sin depender del día que se abra: La App Móvil **no carga una curva repetitiva**. Incorpora un **motor estocástico predictivo** interno. 
- Al abrir la App, distribuye dinámicamente horas productivas hacia la mañana, ocio a mediodía (almuerzos), esparciendo estados inactivos basándose en el biorritmo genérico (ruido de base `IS +/- 10%`).
- Esto garantiza curvas completamente orgánicas y realistas que disparan la alarma a horas de pico naturales según el histórico del `UserIdx`.

### 8.4 Implementación en App Móvil
La app móvil (`gem - phone/mobile.html`) implementa **notificaciones inmersivas "Focus Interventions"** que:
- Oscurecen agresivamente toda la pantalla mediante `backdrop` degradado para interceptar irremediablemente el patrón de scroll (Doom-scrolling).
- Muestran el *IS* instantáneo, minutos devorados, y el mensaje dictaminado sintéticamente por Gemini.
- Empujan **Haptic feedback** vibratorio (`navigator.vibrate([100,50,100])`) disparando alertas cinestésicas.
- Fuerzan la toma de decisión: "Descansar ahora" o "Posponer 15 min".
---

## 9. Productos y Funcionalidades

### 9.1 Dashboard Pitch (`Teyka/index.html`)

Dashboard visual para la presentación del Impacthon. Estética dark Grafana-style.

| Sección | Contenido |
|---|---|
| **Hero** | Estadísticas globales del dataset |
| **IS Live** | Gauge circular + StressScore + BehaviorScore + clasificación de sesiones |
| **Visualización Dual** | Series temporales IS/RMSSD/Pantalla/Pasos + barras intradía |
| **Sistema de Nudge** | Simulador de notificación en smartwatch |
| **Pipeline** | Diagrama visual de la arquitectura |

### 9.2 Panel de Administración (`Teyka/admin.html`)

Panel de investigación para data mining y observabilidad. Dark theme profesional con sidebar.

| Vista | Funcionalidades |
|---|---|
| **Overview** | 6 KPIs globales, histograma IS, comparativa por usuario (barras horizontales), donut Entretenimiento vs Productivo, RMSSD baseline vs diario, Fitbit RMSSD poblacional |
| **Usuarios** | Tabla ordenable y filtrable por PID, IS, pantalla, pasos, sedentarismo. Click en fila → panel de detalle con gráfico IS diario, descomposición Stress vs Behavior, timeline de segmentos entertainment/productive |
| **Correlaciones** | 4 scatter plots: PantallaIS, PasosStress, RMSSDIS, SedentarismoBehavior. Matriz de correlación 5×5 con heatmap |
| **Logs & Alertas** | Tabla de todos los días/usuarios con IS, scores, pannalla, pasos, segmentos. Filtrable por nivel (Crítico/Alerta/Todos). 350+ registros con badges de nivel |
| **Banco de Pruebas** | Simulador de pesos W₁/W₂ con sliders. Recalcula IS en tiempo real y muestra histograma dual (original vs simulado), delta IS, días críticos simulados |
| **Exportar** | Descarga CSV y JSON de todos los datos procesados |

### 9.3 App Móvil (`Teyka - phone/mobile.html`)

App de salud estilo iOS, minimalista, paleta blanco/rojo. Optimizada para móvil con frame de teléfono en desktop.

| Componente | Descripción |
|---|---|
| **Cabecera** | Saludo personalizado (ej. "Hola, Álvaro" dependiente de la hora), fecha y mini-selector de usuario discretamente integrado. |
| **Tooltips SVG Contextuales** | Al mantener el dedo (Hover interaccional) la gráfica dibuja una cruceta de tracking que expone un pequeño icono SVG indicando el estatus real evaluado cognitivamente en ese momento ( Productivo,  Ocio,  Inactivo). |
| **Gauge IS circular** | Anillo SVG animado y texturizado para alto contraste, con color dinámico por nivel. |
| **Gráfico intradía** | Línea ininterrumpida fluida acoplada a una **Threshold Line Punteada ROJA** marcando mecánicamente el umbral del 70%. |
| **Rest Points** | Se visualizan como **Áreas sombreadas en rojo translúcido**, cayendo desde debajo de la curva del Threshold en momentos concretos donde ocurre el *Peligro* para delimitar puramente las zonas "No Productivas" del gráfico. |
| **Selector de rango** | Hoy (24h) / Semana (7 días) / Mes (todos los días). |
| **Health cards** | RMSSD, Pasos, Pantalla y Actividad con barras de progreso métricas e **iconos vectoriales SVG sin emojis** de alta profesionalidad. |
| **Descomposición IS** | StressScore y BehaviorScore con los pesos del motor (0.55 / 0.45). |
| **Historial Dinámico** | Cajas calendáricas interactivas coloreadas, con una curva continua y estadísticas descriptivas matemáticas superpuestas. |
| **Notificación IA** | Pop-up nativo emulando Gemini, recabando métricas al milisegundo y arrojando una alerta inmersiva por saturación Ocio + IS. |

#### 9.4 Onboarding y Personalización (`Teyka - phone/mobile.js`)

Al abrir la app por primera vez, el usuario recorre un **flujo de bienvenida animado** de 6 pasos. Este flujo sólo aparece una vez (persistido en `localStorage`).

| Paso | Pantalla | Descripción |
|---|---|---|
| 0 | **Bienvenida** | Splash con anillo SVG animado pulsante, nombre del proyecto "Teyka" en rojo, y descripción breve. Se auto-avanza a los 3.5 segundos. |
| 1 | **Índice de Saturación** | Tooltip sobre el gauge circular IS. El fondo se vuelve semitransparente (modo tour) para mostrar la app real detrás. |
| 2 | **Gráfica Intradía** | Tooltip explicando las zonas rojas (ocio tóxico) vs azules (productivas) y la línea umbral del 70%. |
| 3 | **Métricas de Salud** | Tooltip apuntando hacia las health cards (RMSSD, Pasos, Pantalla, Actividad). |
| 4 | **Alertas Inteligentes** | Tooltip centrado con previsualización de una notificación de Gemini. |
| 5 | **Selector de Hobbies** | Panel de selección de intereses (12 predefinidos + campo "Otro") que persisten en `localStorage` y alimentan las sugerencias de las notificaciones. |

**Personalización de Notificaciones:**
Los hobbies seleccionados durante el onboarding se almacenan en `localStorage.gem_hobbies`. Cuando el sistema detecta una saturación crítica y genera una notificación Gemini, la función `getHobbySuggestion()` elige aleatoriamente entre los hobbies del usuario para generar sugerencias contextuales como _"pon tu playlist favorita y relájate"_ o _"lee un capítulo de tu libro"_.

**Reset del onboarding (desarrollo/demo):**

Para realizar simulacros durante el Impacthon de forma rápida, puedes forzar el reinicio completo del tour pulsando el atajo de teclado:
**`Shift` + `O`** dentro de la webapp (limpia la caché y recarga la interfaz sola).

Alternativamente, desde la consola del navegador:
```javascript
localStorage.removeItem('gem_onboarded');
localStorage.removeItem('gem_hobbies');
location.reload();
```

---

## 10. Stack Técnico

| Componente | Tecnología |
|---|---|
| ETL / Pipeline | Python 3.x (Pandas, NumPy) |
| Frontend | HTML5, CSS3 (variables CSS, glassmorphism), JavaScript ES6+ nativo |
| Charts | [Chart.js 4.4.4](https://www.chartjs.org/) (CDN) |
| Tipografía | [Inter](https://fonts.google.com/specimen/Inter) + [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) (Google Fonts CDN) |
| Gauge IS | SVG nativo (stroke-dasharray/dashoffset animation) |
| Servidor | `python -m http.server` (desarrollo local) |
| Datos | `gem_data.json` (generado por `extract_gem.py`) |

---

## 11. Estructura Completa de Archivos

```
Impacthon/
│
├── Teyka/                           # Dashboard + Admin Panel
│   ├── extract_gem.py             # ETL v3: IS diario + sesiones → gem_data.json
│   ├── gem_data.json              # Datos procesados (8 usuarios × ~40 días, resolución diaria)
│   ├── index.html                 # Dashboard público (pitch Impacthon)
│   ├── styles.css                 # CSS: dark theme, glassmorphism
│   ├── app.js                     # IS Engine + Charts + Nudge simulator
│   ├── admin.html                 # Panel de investigación (sidebar layout)
│   ├── admin.css                  # CSS: dark research dashboard
│   ├── admin.js                   # Charts, tablas, correlaciones, sandbox, exports
│   └── README.md                  # Esta documentación
│
├── Teyka - phone/                   # App Móvil (usuario final)
│   ├── extract_gem.py             # ETL v4: IS horario intradía → gem_data.json
│   ├── gem_data.json              # Datos procesados (resolución horaria, 24 pts/día)
│   ├── mobile.html                # App SPA (swipeable screens)
│   ├── mobile.css                 # CSS: white/red iOS aesthetic
│   ├── mobile.js                  # Charts Trade Republic + notificaciones
│   ├── index.html                 # Dashboard público (copia)
│   ├── styles.css                 # CSS del dashboard (copia)
│   └── app.js                     # Dashboard logic (copia)
│
├── dataset_final_pitch.csv        # Fitbit RMSSD data (14 usuarios)
├── globem_temp/                   # GLOBEM raw data (4 cohortes)
│   └── GLOBEM-main/data_raw/
│       ├── INS-W-sample_1/FeatureData/{screen,steps}.csv
│       ├── INS-W-sample_2/...
│       ├── INS-W-sample_3/...
│       └── INS-W-sample_4/...
│
├── README.md                      # README raíz
├── WHITE_PAPER.md                 # White paper completo
├── SUMMARY.md                     # Resumen del sistema
├── biometric_inference_fuzzy.md   # Documentación de inferencia difusa
├── dataset_analysis.py            # Análisis exploratorio del dataset
├── globem_analysis.py             # Análisis GLOBEM
└── visualize_metrics.py           # Visualizaciones de métricas
```

---

## 12. Bootstrapping y Deployment

### 12.1 Requisitos Previos

```bash
# Python 3.8+
python --version   # debe ser >= 3.8

# Instalar dependencias
pip install pandas numpy
```

### 12.2 Preparar los Datos

Los datasets deben estar en las rutas relativas correctas antes de ejecutar el ETL:

```
Impacthon/
├── dataset_final_pitch.csv                      ← Fitbit (Kaggle)
├── globem_temp/GLOBEM-main/data_raw/
│   ├── INS-W-sample_1/FeatureData/screen.csv   ← GLOBEM sample 1
│   ├── INS-W-sample_1/FeatureData/steps.csv
│   ├── INS-W-sample_2/FeatureData/screen.csv   ← GLOBEM sample 2
│   ├── INS-W-sample_2/FeatureData/steps.csv
│   ├── INS-W-sample_3/FeatureData/...          ← GLOBEM sample 3
│   └── INS-W-sample_4/FeatureData/...          ← GLOBEM sample 4
```

**Descargar Fitbit data:**
1. Descargar desde [Kaggle Fitbit Dataset](https://www.kaggle.com/arashnic/fitbit)
2. Procesar con `dataset_analysis.py` para generar `dataset_final_pitch.csv`

**Descargar GLOBEM data:**
1. Clonar [GLOBEM repo](https://github.com/UW-EXP/GLOBEM) en `globem_temp/`
2. Los archivos screen.csv y steps.csv ya vienen en el repositorio

### 12.3 Generar datos para Dashboard + Admin (`gem/`)

```bash
cd gem
python extract_gem.py
```

**Output esperado:**
```
Loading Fitbit data...
  Fitbit users: 14, rows: 14
  Population RMSSD baseline: 21.58 ms

Loading GLOBEM data...
  Sample 1: screen=1234, steps=1234
  ...

Merged GLOBEM: 350 rows, 40 participants

Computing IS per day...
Selecting diverse profiles...
  INS-W_617: screen=454min, steps=1668, avg_IS=62.0%
  ...

=== gem_data.json SAVED ===
Fitbit users: 14, GLOBEM users: 8
```

Esto genera `Teyka/gem_data.json` (~718KB) con datos de resolución diaria.

### 12.4 Generar datos para App Móvil (`gem - phone/`)

```bash
cd "gem - phone"
python extract_gem.py
```

Esto genera `gem - phone/gem_data.json` (~2.1MB) con datos de resolución horaria.

### 12.5 Lanzar en Local (Desarrollo)

Para visualizar ambos entornos simultáneamente usando los servidores HTTP de Python:

**Terminal 1 — Dashboard y Admin (Puerto 8096):**
```bash
cd gem
python -m http.server 8096

# Dashboard Web: http://localhost:8096
# Admin Panel:   http://localhost:8096/admin.html
```

**Terminal 2 — App Móvil Teyka (Puerto 8097):**
```bash
cd "gem - phone"
python -m http.server 8097

# App Móvil (Simulador): http://localhost:8097/mobile.html
```

#### Probar Onboarding vs Sin Onboarding (App Móvil)

El User Journey de Teyka incluye una demostración de **Onboarding de primera apertura** y selección de hobbies, controlada a nivel de navegador.

*   **Para probar la app CON el Onboarding (Simular primer uso):**
    Una vez dentro de `localhost:8097/mobile.html`, abre la Consola del Desarrollador (F12) y ejecuta:
    ```javascript
    localStorage.removeItem('gem_onboarded');
    localStorage.removeItem('gem_hobbies');
    location.reload();
    ```
    Verás el Splash Screen, la previsualización interactiva de Teyka AI, el tour dinámico con fondo traslúcido y la asignación de roles.

*   **Para probar la app SIN el Onboarding (Simular uso diario recurrente):**
    Si completas el onboarding pulsando el botón rojo "Empezar" en la tarjeta de aficiones, tu sesión quedará guardada.
    Para simularlo artificialmente sin ver el tour, en consola:
    ```javascript
    localStorage.setItem('gem_onboarded', '1');
    location.reload();
    ```
    La aplicación omitirá el bloqueo, saltando directamente a la Home con el "Resumen de ayer" y las mediciones listas.


> **Tip Mobile:** En Chrome/Edge DevTools (F12), usa el *Device Toolbar Toggle* (`Ctrl+Shift+M`) y selecciona un dispositivo como "iPhone 14 Pro" para manipular la app móvil en su factor de forma nativo y activar los eventos Touch.

### 12.6 Deployment en Producción (Todas las webs)

Al ser aplicaciones 100% estáticas (Vanilla JS/HTML/CSS sin Backend), servidas sobre el JSON estático pre-computado (`gem_data.json`), su despliegue es trivial, increíblemente rápido y altamente escalable.

Se recomienda la siguiente topología de accesos:
- `Teyka.tudominio.com` → Pitch Dashboard (Público)
- `Teyka.tudominio.com/admin.html` → Admin Panel (Investigadores)
- `app.Teyka.com` *(o Teyka.tudominio.com/app)* → App Móvil (Usuario final)

#### Opción A — Servidor Nginx (Recomendado para VPS propios)

Ejemplo de bloque `server` para configurar ambos productos en el mismo host pero con directorios segregados:

```nginx
server {
    listen 80;
    server_name Teyka.tudominio.com;

    # Producto 1: Dashboard y Admin (Root path)
    location / {
        alias /var/www/Teyka/;
        index index.html;
        try_files $uri $uri/ =404;
    }

    # Producto 2: App Móvil (Sub-path)
    location /app/ {
        alias /var/www/Teyka-phone/;
        index mobile.html;
        try_files $uri $uri/ =404;
    }
}
```
*Pasos:* 
1. Subir contenidos de `Teyka/` a `/var/www/Teyka/`
2. Subir contenidos de `Teyka - phone/` a `/var/www/Teyka-phone/`
3. Asegurar que cada carpeta incluye su respectivo `gem_data.json`.

#### Opción B — Vercel / Netlify / Cloudflare Pages (Serverless)

La forma más rápida. Se deben crear **dos proyectos separados** en tu cuenta (ej. en Vercel):

**Proyecto 1 (Web Principal):**
- Conectar Repositorio GitHub.
- **Root Directory:** `Teyka/`
- **Build Command:** *(dejar vacío)*
- **Output Directory:** `.` o `Teyka/`

**Proyecto 2 (La App):**
- Conectar Repositorio GitHub.
- **Root Directory:** `Teyka - phone/`
- **Build Command:** *(dejar vacío)*
- Opcionalmente añade un *Redirect* en la configuración del proveedor para que la raíz `/` envíe automáticamente a `/mobile.html`.

#### Opción C — Embalaje Docker 

Si requieres llevar todo a contenedores (Kubernetes/ECS), un `Dockerfile` unificado usando Nginx Alpine:

```dockerfile
FROM nginx:alpine
RUN rm -rf /usr/share/nginx/html/*

# Copia de Dashboard
COPY ./Teyka /usr/share/nginx/html/
# Copia de Mobile app en subcarpeta app/
COPY ./Teyka\ -\ phone /usr/share/nginx/html/app/

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

>  **Advertencia de Datos Crítica:** Recuerda siempre ejecutar `python extract_gem.py` en ambas plataformas después de cualquier cambio en el motor o en los datasets base, antes de desplegar. El motor se ejecuta pre-runtime, no durante. Si `gem_data.json` no se sube compilado, las webs fallarán sin mostrar métricas.

---

## 13. Decisiones de Diseño

### ¿Por qué sigmoide logística para el BehaviorScore?
La normalización lineal (`screen / 600`) satura abruptamente y no captura la relación dosis-respuesta real. La sigmoide logística sobre la Carga Digital compuesta (CD):
- Modela correctamente la curva de toxicidad digital (poco impacto al inicio, aceleración, saturación)
- Es diferenciable en todo el dominio (útil para futuro aprendizaje automático)
- Integra pantalla, desbloqueos y pasos en una sola métrica compuesta
- El punto de inflexión θ=280 CD units corresponde a ~4.5h de pantalla con uso moderado

### ¿Por qué pesos 0.55/0.45?
Inicialmente se usó 0.60/0.40, pero tras calibración:
- Con 0.60/0.40, el StressScore dominaba y causaba saturación (100% constante) en usuarios sedentarios
- Con 0.55/0.45, el BehaviorScore (que incluye la sigmoide CD + clasificación de sesiones) tiene influencia suficiente para que el IS responda a los patrones de uso real

### ¿Por qué RMSSD sintético?
Los datasets Fitbit y GLOBEM son de usuarios **diferentes**. No podemos vincular directamente el RMSSD real de un usuario Fitbit con la conducta de un usuario GLOBEM. Por ello, generamos un RMSSD sintético per-usuario GLOBEM que:
- Tiene una **baseline calibrada** con la distribución real de RMSSD de Fitbit (media poblacional: 21.58 ms)
- **Varía diariamente** en función de la conducta digital y la actividad física
- Mantiene la **correlación clínica** validada: más pantalla + menos pasos → RMSSD baja → estrés sube

### ¿Por qué clasificación relativa per-usuario?
La v1 usaba umbrales absolutos (`avg_session > 10 min && steps < 500`). Esto causaba que:
- Usuarios activos (22k pasos) **nunca** se clasificaran como entretenimiento
- Usuarios sedentarios **siempre** fueran entretenimiento

La v2 usa percentiles del propio usuario, de modo que cada persona se compara **consigo misma**: un usuario activo puede tener entretenimiento cuando está inusualmente quieto con pantalla alta.

### ¿Por qué dos versiones del ETL?
- El **dashboard de presentación** necesita datos diarios con clasificación de sesiones para las gráficas de la demo
- La **app móvil** necesita datos horarios para el gráfico intradía estilo Trade Republic, que requiere mayor granularidad temporal

### ¿Por qué paleta blanco/rojo para la app móvil?
Se eligió una paleta minimalista blanco/rojo inspirada en Apple Health y Trade Republic porque:
- El rojo señala **urgencia** sin ser agresivo
- El blanco mantiene la **claridad** y legibilidad
- Los niveles de saturación se comunican intuitivamente: más rojo = más saturación
