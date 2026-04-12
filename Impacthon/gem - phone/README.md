# Proyecto Teyka — Documentación Técnica Completa

> **Gestión del Estado Nervioso**  
> De la biometría pasiva a la intervención proactiva.  
> Impacthon 2026 — USC

---

## 1. Visión General

El Proyecto Teyka propone un cambio de paradigma: pasar del **bloqueo reactivo de aplicaciones** a la **gestión proactiva del estado nervioso**. Utilizamos la biometría como "alarma temprana" de la pérdida de autorregulación cognitiva.

El sistema calcula un **Índice de Saturación (IS)** en tiempo real que combina estrés fisiológico (variabilidad cardíaca) con patrones de comportamiento digital (uso de pantalla, actividad física). Cuando el IS supera el 75%, el sistema genera una **intervención proactiva (Nudge)** sugiriendo actividades alternativas.

### Referencia Académica

> Wang, R., Chen, F., Chen, Z. et al. «StudentLife: Assessing Mental Health, Academic Performance and Behavioral Trends of College Students using Smartphones», ACM UbiComp, 2021.

---

## 2. Datasets Utilizados

### 2.1 Fitbit — Fitabase (Kaggle)

- **Fuente:** [Fitbit Fitness Tracker Data](https://www.kaggle.com/arashnic/fitbit) via Fitabase
- **Registros:** 2.4 millones de mediciones de frecuencia cardíaca segundo a segundo
- **Participantes:** 14 usuarios
- **Variables extraídas:**
  - **RMSSD (ms):** Root Mean Square of Successive Differences — métrica gold-standard de la Variabilidad de la Frecuencia Cardíaca (HRV). Calculada a partir de los Inter-Beat Intervals (IBI) derivados de `heartrate_seconds`.
  - **SedentaryMinutes:** Minutos de sedentarismo registrados por Fitbit (acelerómetro).
  - **Perfil de Riesgo:** Clasificación derivada del RMSSD (Alto/Medio/Bajo).
- **Uso en el sistema:** Establece la **baseline poblacional de RMSSD** (21.58 ms) y proporciona los datos de referencia para calibrar los umbrales de estrés fisiológico.

### 2.2 GLOBEM — UW EXP Lab

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

## 3. Pipeline ETL (`extract_gem.py`)

### 3.1 Ingesta

```
Fitbit (dataset_final_pitch.csv)
    ├── RMSSD por usuario (baseline poblacional)
    └── SedentaryMinutes (referencia Fitbit)

GLOBEM (4 cohortes × screen.csv + steps.csv)
    ├── Merge por (pid, date)
    ├── Renombrado de columnas RAPIDS → nombres legibles
    └── Filtrado: dropna en screen_min_allday y steps_allday
```

### 3.2 Cálculo de Baselines por Usuario

```python
# Ratio de actividad: qué fracción de las 16h despierto es activa
activity_ratio = active_min_allday / 960  # rango 0 a ~0.7

# RMSSD baseline: más actividad → mejor tono vagal → baseline más alta
synth_rmssd_baseline = 20 + activity_ratio * 20  # rango 20-34 ms
```

**Justificación clínica:** El RMSSD mide tono vagal (activación parasimpática). La evidencia muestra que el sedentarismo crónico reduce el tono vagal basal — el nervio vago pierde capacidad de regulación. Esto se traduce en menor resiliencia al estrés agudo.

**Ejemplo por usuario:**

| Usuario | Active min/día | Activity Ratio | Baseline RMSSD |
|---|---|---|---|
| Sedentario (57 min activo) | 57 | 0.059 | 21.2 ms |
| Moderado (194 min activo) | 194 | 0.202 | 24.0 ms |
| Activo (350 min activo) | 350 | 0.365 | 27.3 ms |

### 3.3 Selección de Usuarios Diversos

Se seleccionan **8 usuarios** representativos con perfiles extremos y medios:
- 2 con **más pantalla** (>600 min/día)
- 2 con **menos pantalla** (<130 min/día)
- 2 con **más pasos** (>19k pasos/día)
- 2 con **más sedentarismo** corregido
- Relleno hasta 8 con usuarios intermedios

---

## 4. Índice de Saturación (IS)

### 4.1 Fórmula

```
IS = 0.55 × StressScore + 0.45 × BehaviorScore
```

El IS combina dos dimensiones independientes:
- **StressScore (55%):** Estado fisiológico del sistema nervioso autónomo
- **BehaviorScore (45%):** Patrón de comportamiento digital

### 4.2 StressScore — Componente Fisiológico

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

**Desglose del mecanismo:**

| Factor | Peso en la caída | Justificación |
|---|---|---|
| Pantalla | 60% | Estímulo principal de hiperfocalización y activación simpática |
| Sedentarismo | 40% | Reduce activación parasimpática por inmovilidad prolongada |
| Pasos (protección) | Hasta -40% | La actividad física favorece la regulación vagal |

**Ejemplo numérico:**

```
Usuario con baseline 24 ms:
  - Pantalla: 400 min → screen_norm = 0.67
  - Sedentarismo: 800 min → sed_norm = 0.89
  - Pasos: 5000 → protection = 0.17
  
  rmssd_drop = (0.67×0.6 + 0.89×0.4) × 12 × (1 - 0.17)
             = (0.40 + 0.36) × 12 × 0.83
             = 0.76 × 9.96 = 7.5 ms
  
  daily_rmssd = 24 - 7.5 = 16.5 ms
  stress_score = (24 - 16.5) / 24 × 100 = 31.3%
```

### 4.3 BehaviorScore — Componente Conductual

El BehaviorScore evalúa la calidad del uso digital combinando inercia de pantalla, clasificación de sesiones y penalización nocturna.

```python
# 1. Inercia: ratio pantalla / (pantalla + actividad efectiva)
eff_activity = active_min + steps / 150
inertia = screen / max(screen + eff_activity, 1)  # 0 a 1

# 2. Clasificación de sesiones (ver sección 5)
ent_count = nº segmentos clasificados como "entretenimiento"  # 0 a 4

# 3. Penalización por entretenimiento: 15 pts por segmento
ent_penalty = ent_count × 15  # 0 a 60

# 4. Penalización nocturna: pantalla >30 min en horario 00:00-06:00
night_penalty = min(night_screen / 60, 1) × 10  # 0 a 10

# 5. Score final
behavior_score = min(inertia × 65 + ent_penalty + night_penalty, 100)
```

**Rangos típicos:**

| Perfil | Inertia | Ent Segments | BehaviorScore |
|---|---|---|---|
| Saludable (150 min pantalla, 20k pasos) | 0.10 | 0-1 | 7-22 |
| Moderado (400 min pantalla, 8k pasos) | 0.42 | 1-2 | 42-57 |
| Problemático (600 min pantalla, 2k pasos) | 0.82 | 2-4 | 83-100 |

### 4.4 Garantías de Consistencia

Para asegurar que la clasificación de sesiones siempre correlacione con el IS:

```python
if ent_count >= 2: IS = max(IS, 50)    # 2+ segmentos ent → IS ≥ 50%
if ent_count >= 3: IS = max(IS, 65)    # 3+ segmentos ent → IS ≥ 65%
if ent_count >= 3 and screen > p75:    # 3+ ent + pantalla alta → IS ≥ 75%
    IS = max(IS, 75)
if ent_count == 4: IS = max(IS, 78)    # 4 segmentos ent → IS ≥ 78%
if screen > 500 and steps < 3000:      # Pantalla extrema + inactividad → IS ≥ 75%
    IS = max(IS, 75)
```

### 4.5 Umbral de Alerta

Cuando **IS > 75%**, el sistema activa la intervención proactiva (Nudge).

---

## 5. Clasificación de Sesiones: Productivo vs. Entretenimiento

### 5.1 Principio

No tenemos datos de qué aplicación usa cada persona. La clasificación se basa en el **patrón de uso del móvil** cruzado con la **actividad física** en cada segmento del día. Es una **inferencia conductual**.

### 5.2 Umbrales Personalizados (Per-User Percentiles)

Para cada usuario se calculan umbrales relativos a su propio historial:

```python
# Para cada segmento (morning, afternoon, evening, night):
screen_p50 = percentil 50 del tiempo de pantalla del usuario en ese segmento
screen_p75 = percentil 75
steps_p25  = percentil 25 de pasos del usuario en ese segmento
```

Esto evita el problema de comparar un usuario activo (22k pasos/día) con uno sedentario (2k pasos/día) usando umbrales absolutos.

### 5.3 Reglas de Clasificación

####  Productivo
Un segmento se clasifica como **productivo** cuando:
- El tiempo de pantalla está **por debajo de la mediana** del usuario para ese segmento
- **O** los pasos están **por encima del percentil 25** del usuario
- **O** hay muchos desbloqueos con sesiones cortas (patrón de "check-and-go")

**Interpretación:** Uso funcional del móvil — consultas rápidas, mensajes, mientras se mantiene actividad.

####  Entretenimiento
Un segmento se clasifica como **entretenimiento** cuando se cumplen **dos condiciones simultáneas**:

1. **Pantalla por encima de la mediana** del usuario para ese segmento
2. **Y al menos una** señal de absorción pasiva:
   - **Pasos bajos** (< percentil 25) → sentado/tumbado
   - **Patrón binge:** ≤5 desbloqueos con sesión media >15 min → pocas sesiones pero muy largas (scrolling infinito, streaming)
   - **Sesión dominante:** una sesión >30 min que ocupa >60% del tiempo total del segmento → una sola actividad monopoliza el uso

**Interpretación:** Absorción pasiva en el móvil con inmovilidad prolongada.

####  None
Si el tiempo de pantalla en ese segmento es <3 minutos → dato insuficiente.

### 5.4 Señales Conductuales

| Señal | Productivo | Entretenimiento |
|---|---|---|
| Duración de sesiones | Cortas, frecuentes | Largas, pocas |
| Desbloqueos | Muchos (>5) | Pocos (≤5) |
| Pasos durante uso | Normales/altos | Bajos |
| Pantalla total | ≤ mediana del usuario | > mediana del usuario |
| Sesión máxima | <30 min o <60% del total | >30 min y >60% del total |

---

## 6. Rol del Sedentarismo en el Estrés

El sedentarismo impacta el estrés a través de **dos mecanismos**:

### 6.1 Baseline RMSSD (Efecto Crónico)
Un usuario con más sedentarismo medio tiene un RMSSD basal más bajo (peor tono vagal). Esto simula que una persona crónicamente sedentaria tiene un sistema nervioso autónomo de partida más débil.

```
Mismo uso de pantalla (400 min):
  - Usuario sedentario (baseline 21 ms): StressScore ≈ 35%
  - Usuario activo (baseline 27 ms): StressScore ≈ 28%
```

El mismo estímulo digital genera +7 puntos más de estrés en el usuario sedentario.

### 6.2 sed_norm Diario (Efecto Agudo)
El sedentarismo del día (corregido: 960 - active_min) contribuye al 40% de la caída del RMSSD. Un día con 900 min de sedentarismo diurno provoca la caída máxima.

### 6.3 Dónde se visualiza

- **KPI "Sedentarismo":** Minutos de sedentarismo diurno corregido (600-900 min típico)
- **KPI "RMSSD Synth.":** Valor diario del RMSSD sintético — usuarios sedentarios = valores base más bajos
- **StressScore:** El valor numérico refleja la amplificación del estrés por sedentarismo

---

## 7. Sistema de Nudge

### 7.1 Trigger
Cuando IS > 75%, el sistema activa la intervención proactiva.

### 7.2 Flujo del Nudge

```
1.  Monitoreo Pasivo
   → Smartwatch captura RMSSD, móvil registra pantalla y actividad

2.  Motor IS
   → StressScore + BehaviorScore → IS > 75% → Trigger

3.  Nudge Contextual
   → Sugerencia de actividad alternativa adaptada al perfil

4.  Aprendizaje Continuo
   → Feedback del usuario ajusta pesos para futuras intervenciones
```

### 7.3 Ejemplos de Sugerencias

Las sugerencias se basan en los datos biométricos del momento:

- "Llevas **5h 23min** de pantalla. Sal a **caminar 15 min** — tu HRV mejorará un 20%."
- "Tu sistema nervioso necesita un **descanso**. Prueba **10 min de respiración** guiada."
- "Tu RMSSD ha caído un **30%**. Deja el móvil y **sal a pasear**."

---

## 8. Dashboard Técnico

### 8.1 Stack

| Componente | Tecnología |
|---|---|
| ETL / Pipeline | Python (Pandas, NumPy) |
| Frontend | HTML5, CSS3 (Glassmorphism sobrio), JS Nativo |
| Charts | Chart.js 4.4.4 |
| Tipografía | Inter + JetBrains Mono (Google Fonts) |
| Datos | `gem_data.json` (generado por `extract_gem.py`) |

### 8.2 Secciones del Dashboard

1. **Hero** — Estadísticas globales del dataset
2. **IS Live** — Gauge circular + StressScore + BehaviorScore + clasificación de sesiones + KPIs + timeline con simulación temporal
3. **Visualización Dual** — Gráficas Chart.js: serie temporal IS/RMSSD/Pantalla/Pasos + barras intradía por segmento
4. **Sistema de Nudge** — Simulador de notificación en smartwatch con vibración
5. **Pipeline** — Diagrama visual de la arquitectura de datos

### 8.3 Simulación Temporal

El dashboard incluye un reproductor temporal que avanza día a día por el historial de cada usuario:
- **Velocidades:** 7s (lenta) / 3.5s (media) / 1.5s (rápida) por transición
- Al avanzar, se actualizan en tiempo real: gauge IS, scores, clasificación de sesiones, KPIs, y highlight en la gráfica temporal
- Cuando IS > 75%, aparece un banner de alerta rojo con sugerencia

---

## 9. Estructura de Archivos

```
Teyka/
├── extract_gem.py      # Pipeline ETL: Fitbit + GLOBEM → gem_data.json
├── gem_data.json       # Datos procesados (8 usuarios × ~40 días)
├── index.html          # Dashboard SPA
├── styles.css          # CSS: dark theme, glassmorphism sobrio
├── app.js              # IS Engine + Charts + Nudge simulator
└── README.md           # Esta documentación
```

---

## 10. Cómo Ejecutar

### Generar datos
```bash
cd Teyka
python extract_gem.py
```

Requiere:
- `../dataset_final_pitch.csv` (Fitbit procesado)
- `../globem_temp/GLOBEM-main/data_raw/INS-W-sample_*/FeatureData/` (GLOBEM raw)

### Lanzar dashboard
```bash
cd Teyka
python -m http.server 8080
# Abrir http://localhost:8080
```

---

## 11. Decisiones de Diseño

### ¿Por qué RMSSD sintético?
Los datasets Fitbit y GLOBEM son de usuarios **diferentes**. No podemos vincular directamente el RMSSD real de un usuario Fitbit con la conducta de un usuario GLOBEM. Por ello, generamos un RMSSD sintético per-usuario GLOBEM que:
- Tiene una **baseline calibrada** con la distribución real de RMSSD de Fitbit (media poblacional: 21.58 ms)
- **Varía diariamente** en función de la conducta digital y la actividad física
- Mantiene la **correlación clínica** validada: más pantalla + menos pasos → RMSSD baja → estrés sube

### ¿Por qué pesos 0.55/0.45?
Inicialmente se usó 0.60/0.40, pero tras calibración:
- Con 0.60/0.40, el StressScore dominaba y causaba saturación (100% constante) en usuarios sedentarios
- Con 0.55/0.45, el BehaviorScore (que incluye la clasificación de sesiones) tiene más influencia, haciendo que el IS responda mejor a los patrones de uso real

### ¿Por qué clasificación relativa per-usuario?
La v1 usaba umbrales absolutos (`avg_session > 10 min && steps < 500`). Esto causaba que:
- Usuarios activos (22k pasos) **nunca** se clasificaran como entretenimiento
- Usuarios sedentarios **siempre** fueran entretenimiento

La v2 usa percentiles del propio usuario, de modo que cada persona se compara **consigo misma**: un usuario activo puede tener entretenimiento cuando está inusualmente quieto con pantalla alta.
