# 📱⌚ WristGuard
### *Tu cuerpo sabe cuándo parar. Nosotros te lo decimos.*

> Los smartwatches ya deciden cuándo despertarte.  
> ¿Por qué no pueden decirte cuándo dejar el móvil?

---

## 🧭 El problema

Vivimos pegados al móvil — y lo sabemos. Pero saberlo no es suficiente para parar.

Las apps de control de tiempo de pantalla fallan porque ponen límites arbitrarios basados en el reloj, no en cómo está tu cuerpo. Dos horas de scroll ansioso a las 11 de la noche no son iguales que dos horas de vídeos relajado en el sofá. Nuestro cerebro y nuestro cuerpo saben la diferencia. Hasta ahora, nuestro móvil no.

**WristGuard** escucha a tu cuerpo y te dice cuándo es el momento óptimo para tomar un descanso — no antes, no después.

---

## 📊 El contexto: los números respaldan la oportunidad

### Usamos el móvil demasiado — y cada vez más

- **6h 34min** al día de media pasa una persona conectada a internet (DataReportal, 2025)
- El tiempo de uso de apps móviles a nivel mundial **aumentó un 30% desde 2019**
- Los jóvenes de **18 a 24 años** lideran con **5,7 horas diarias** de uso de internet (INEGI, 2024)
- En España, el **92,5% de la población** usa internet a diario (INE, 2025)

### Y queremos usarlo menos

- **1 de cada 3 consumidores** en Latinoamérica espera reducir sus actividades digitales (Bain & Company, 2025)
- El **25%** asocia la actividad digital a daños en su salud y bienestar
- El bienestar digital es uno de los **temas más buscados en Reddit y Quora** en 2025: límites de apps, gestión de notificaciones, cómo desconectarse
- La categoría "detox digital" no deja de crecer en búsquedas, podcasts y libros

### El mercado de smartwatches está listo

- **528 millones de personas** tienen smartwatch en 2026 — creciendo al 14,2% anual
- **40% de los adultos de 18-34 años** ya tiene un smartwatch — nuestro público objetivo exacto
- El **92% de los usuarios** los usa para salud y fitness — ya están en el mindset correcto
- **Gen Z (11-26 años)**: 41% de penetración, impulsada por apps de bienestar
- El mercado global alcanza **$118,4 billones en 2025** y proyecta $142 billones en 2034

> 💡 **La intersección perfecta:** un usuario que ya usa smartwatch + quiere cuidar su salud + está harto de usar demasiado el móvil. Ese usuario existe, es masivo, y no tiene una solución real todavía.

---

## 💡 La solución: WristGuard

WristGuard es una aplicación para **smartwatch + móvil** que entrena un modelo de Machine Learning personalizado para determinar, en tiempo real, cuándo es el mejor momento para que *tú específicamente* tomes un descanso del móvil.

No funciona con límites de tiempo arbitrarios.  
Funciona midiendo cómo responde **tu cuerpo** al uso de tu móvil.

### ¿Qué lo hace diferente?

| Solución actual | WristGuard |
|---|---|
| "Llevas 2h en TikTok. Parar." | "Tu ritmo cardíaco subió un 18%, llevas 40min sin moverte y son las 23:30. Es un buen momento para parar." |
| Límites arbitrarios por tiempo | Intervención basada en estado fisiológico real |
| Igual para todo el mundo | Modelo personalizado que aprende de ti |
| Caja negra | Explicación en lenguaje natural de por qué te lo dice |
| Reactivo (te bloquea) | Proactivo (te sugiere en el momento óptimo) |

---

## 🏗️ Arquitectura técnica

### Fuentes de datos

```
┌─────────────────────────────────────┐     ┌──────────────────────────────────────┐
│         SMARTWATCH                  │     │           SMARTPHONE                 │
│                                     │     │                                      │
│  • Frecuencia cardíaca (HR)         │     │  • Duración de sesión activa         │
│  • Variabilidad cardíaca (HRV)      │     │  • Tiempo total de pantalla hoy      │
│  • Pasos / movimiento               │     │  • Categoría de app en uso           │
│  • Calidad y duración del sueño     │     │  • Frecuencia de desbloqueos         │
│  • SpO2 (saturación de oxígeno)     │     │  • Tasa de notificaciones            │
│  • Tiempo sin movimiento            │     │  • Hora del día / día de la semana   │
└─────────────────────────────────────┘     └──────────────────────────────────────┘
                    │                                         │
                    └──────────────┬──────────────────────────┘
                                   ▼
                        Feature Engineering
                    (ventanas de 5, 15, 30 min)
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Capa 1: Inferencia Borrosa   │
                    │  (Sistema Mamdani)            │
                    │                              │
                    │  HRV_index    [0.0 – 1.0]    │
                    │  HR_stress    [0.0 – 1.0]    │
                    │  bio_digital_risk             │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Capa 2: Modelo GBT           │
                    │  LightGBM + SHAP              │
                    │                              │
                    │  optimal_stop_score          │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    Intervención en el smartwatch
                    con explicación en lenguaje natural
```

### Features del modelo

#### Biométricas (smartwatch)

| Feature | Descripción | Por qué importa |
|---|---|---|
| `hrv_delta_30min` | Caída de HRV vs. baseline personal | Fatiga mental acumulándose |
| `hr_above_baseline` | BPM actual - BPM en reposo personal | Activación del sistema nervioso simpático |
| `movement_gap_min` | Minutos desde último movimiento significativo | Sedentarismo físico directo |
| `spO2_drop` | Desviación vs. baseline | Postura encorvada sostenida ("text neck") |
| `sleep_debt_hours` | Déficit acumulado últimas 72h | El cuerpo ya viene deteriorado |
| `sleep_last_night_quality` | Score 0-1 basado en fases de sueño | Base de recuperación del día |

#### Uso del móvil (smartphone)

| Feature | Descripción | Por qué importa |
|---|---|---|
| `session_duration_current` | Duración de la sesión activa | La sesión en curso |
| `total_screen_today` | Tiempo total de pantalla hoy | Acumulación diaria |
| `app_category` | Categoría de la app activa | Redes sociales ≠ trabajo ≠ vídeo |
| `unlock_frequency_hour` | Desbloqueos en la última hora | Comportamiento compulsivo |
| `notification_rate_15min` | Notificaciones en 15 min | Fragmentación atencional |
| `hour_of_day` + `is_night` | Contexto temporal | El uso nocturno es más dañino |

#### Features derivadas (las más potentes)

| Feature | Cálculo | Intuición |
|---|---|---|
| `bio_digital_divergence` | `hr_above_baseline × session_duration` | Cuerpo activado + uso largo = señal fuerte |
| `recovery_debt_index` | `sleep_debt + movement_gap - hrv_delta` | Cuánto debe el cuerpo ya |
| `compulsion_score` | `unlock_frequency / session_duration` | Muchos desbloqueos, sesiones cortas |
| `night_bio_risk` | `is_night × hr_elevated × session_duration` | Multiplicador nocturno |
| `context_stress_load` | Combinación HRV + notificaciones + hora | Carga cognitiva estimada |
| `bio_digital_risk` ⭐ | `hr_stress_fuzzy × (1 - hrv_index_fuzzy) × session_norm` | **Cuerpo activado + HRV baja + uso prolongado** |

> ⭐ `bio_digital_risk` es la feature esperada en top-3 SHAP: tiene respaldo clínico directo e integra la salida del sistema borroso.

---

## 📦 Dataset

### Dataset principal: GLOBEM (PhysioNet)

Dataset longitudinal de **4 años (2018-2021)** recogido en una universidad R-1 americana. Es uno de los pocos datasets públicos que combina datos de móvil y wearable **del mismo sujeto** con granularidad temporal.

```
GLOBEM/
├── screen.csv       → PhoneUsage: tiempo de pantalla, desbloqueos
├── steps.csv        → PhysicalActivity: pasos, sedentarismo
├── sleep.csv        → Sleep: duración, calidad, fragmentación
├── location.csv     → Location: movilidad, rutinas
├── call.csv         → Call: patrones de comunicación
├── bluetooth.csv    → Bluetooth: interacción social
└── dep_weekly.csv   → Labels: bienestar semanal (EMA surveys)
```

Cada feature está segmentada por franja horaria: `morning`, `afternoon`, `evening`, `night`, `allday`, `7dhist`, `14dhist`.

### ¿Por qué GLOBEM?

- ✅ **Datos reales** — recogidos en condiciones de vida real, no en laboratorio
- ✅ **Mismo sujeto** — móvil + wearable del mismo individuo simultáneamente
- ✅ **Granularidad temporal** — segmentación por franjas horarias
- ✅ **Labels de bienestar** — permiten construir el target variable
- ✅ **Longitudinal** — 4 años, captura evolución y cambios de hábitos

### Complemento: Inferencia de variables latentes

GLOBEM no incluye HRV ni frecuencia cardíaca directamente. Las inferimos mediante un **sistema de lógica borrosa Mamdani** entrenado sobre correlatos comportamentales documentados en la literatura clínica:

```python
HRV_index   = fuzzy_mamdani(sleep_quality, sleep_debt, daily_steps, screen_night)
HR_stress   = fuzzy_mamdani(daily_steps, sleep_debt, screen_night, unlock_frequency)
```

> En producción, estos proxies se sustituyen por señales directas del smartwatch y la Screen Time API. El modelo no cambia — solo mejora.

---

## 🧠 Capa 1: Inferencia Borrosa (Sistema Mamdani)

### ¿Por qué lógica borrosa?

La biología no es binaria. El estrés no es "sí/no". La fatiga no aparece de golpe. Los estados fisiológicos son **graduales, solapados y dependientes del contexto** — exactamente el dominio para el que se diseñaron los conjuntos borrosos (Zadeh, 1965).

Un sistema de reglas nítidas fallaría porque:
- Una persona sedentaria tiene un baseline distinto a una deportista
- El mismo HRV bajo puede indicar recuperación post-ejercicio o estrés crónico
- Las variables interactúan — sueño malo + pantalla nocturna es peor que cada uno por separado

La lógica borrosa captura estas gradaciones mediante **grados de pertenencia [0,1]** en lugar de umbrales duros, y sus reglas combinan variables de forma no lineal. Está respaldada directamente por la literatura: sistemas Mamdani han sido validados para estimación de estrés fisiológico con precisión dentro de 10 segundos (Zalabarria et al., IEEE Access 2020; Sierra et al., IEEE Trans. Ind. Electron. 2011).

### Variables de entrada y conjuntos borrosos

| Variable | Universo | Conjuntos | Ancla clínica |
|---|---|---|---|
| `sleep_quality` | [0, 10] | POBRE / REGULAR / BUENA | PSQI > 5 = sueño pobre (validado en >100 estudios) |
| `sleep_debt` | [0, 72h] | BAJO / MODERADO / ALTO | >3h = deterioro cognitivo significativo |
| `daily_steps` | [0, 20000] | MUY_SEDENTARIO / SEDENTARIO / ACTIVO / MUY_ACTIVO | Umbrales OMS/CDC |
| `screen_night` | [0, 480 min] | NINGUNO / MODERADO / EXCESIVO | >60 min = supresión melatonina significativa |

Todas las funciones de pertenencia son **trapezoidales** — robustas y con transiciones graduales.

### Variables de salida

| Salida | Rango | Conjuntos | Ancla clínica |
|---|---|---|---|
| `HRV_index` | [0.0, 1.0] | MUY_BAJA / BAJA / NORMAL / ALTA | RMSSD <25 ms = inhibición vagal; >50 ms = parasimpático saludable |
| `HR_stress` | [0.0, 1.0] | RELAJADO / LIGERAMENTE_ELEVADO / ELEVADO / MUY_ELEVADO | +0.24 bpm/hora sedentaria (meta-análisis MDPI 2021) |

### Base de reglas clínicas (selección)

Las reglas siguen la forma **SI [condición borrosa] ENTONCES [consecuente borroso]** con un peso que refleja la fuerza de la evidencia:

```
R1:  SI sueño=POBRE  ∧ pasos=MUY_SEDENTARIO
     → HRV=MUY_BAJA                          [peso 0.95]
     Ref: ScienceDirect 2024 (correlación PSQI-SDNN)

R2:  SI sueño=POBRE  ∧ pantalla_nocturna=EXCESIVA
     → HRV=MUY_BAJA                          [peso 0.90]
     Ref: Lemola 2015 + Frontiers Physiology 2025

R5:  SI sueño=BUENA  ∧ pasos=MUY_ACTIVO
     → HRV=ALTA                              [peso 0.90]
     Ref: Frontiers Physiology 2025 (HIIT-RMSSD)

R9:  SI pasos=MUY_SEDENTARIO ∧ pantalla_nocturna=EXCESIVA ∧ hora=NOCHE
     → HR_stress=MUY_ELEVADO                 [peso 0.90]
     Ref: Sedentary Behaviour & Psychobiology, ScienceDirect 2022

R14: SI hora=NOCHE ∧ sesion_activa=LARGA ∧ sueño=POBRE
     → HR_stress=MUY_ELEVADO                 [peso 0.93]
     Efecto multiplicador nocturno con deuda de sueño

R15: SI sueño=POBRE ∧ pasos=MUY_SEDENTARIO
       ∧ pantalla_nocturna=EXCESIVA ∧ deuda_sueño=ALTA
     → HRV=MUY_BAJA ∧ HR_stress=MUY_ELEVADO  [peso 0.97]
     ★ "Tormenta perfecta" — Ref: Sleep Journal 2023, MIDUS II n=966
```

La regla R15 es la más importante: captura la **sinergia entre variables** que ningún sistema de umbral nítido puede representar.

### Ejemplo de inferencia paso a paso

Inputs observados a las **21:45** de un usuario típico:

```python
sleep_quality_score  = 0.35   # Sueño pobre anoche (PSQI ≈ 7)
sleep_debt_hours     = 2.5    # Déficit acumulado semanal
daily_steps          = 2200   # Muy sedentario
screen_night_min     = 85     # 85 min de pantalla nocturna
```

**Paso 1 — Fuzzificación:**
```
sleep_quality → μ_POBRE=0.72, μ_REGULAR=0.28, μ_BUENA=0.00
sleep_debt    → μ_BAJO=0.00,  μ_MODERADO=0.75, μ_ALTO=0.25
daily_steps   → μ_MUY_SED=0.85, μ_SED=0.15, μ_ACTIVO=0.00
screen_night  → μ_NINGUNO=0.00, μ_MODERADO=0.12, μ_EXCESIVO=0.88
```

**Paso 2 — Evaluación de reglas (t-norma mínimo):**
```
R1:  min(0.72, 0.85) = 0.72  → HRV_MUY_BAJA  activada con fuerza 0.72
R2:  min(0.72, 0.88) = 0.72  → HRV_MUY_BAJA  activada con fuerza 0.72
R6:  min(0.88, 0.75) = 0.75  → HRV_BAJA      activada con fuerza 0.75
R15: min(0.72, 0.85, 0.88, 0.25) = 0.25
     → HRV_MUY_BAJA + HR_stress_MUY_ELEVADO activados con fuerza 0.25
```

**Paso 3 — Defuzzificación (método centroide):**
```python
HRV_index  = 0.18   # "muy baja"    (escala 0–1)
HR_stress  = 0.83   # "muy elevado" (escala 0–1)
```

### Implementación

```python
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# ── Antecedentes ─────────────────────────────────────────────────────
sleep_quality = ctrl.Antecedent(np.arange(0, 11, 0.1),    'sleep_quality')
sleep_debt    = ctrl.Antecedent(np.arange(0, 73, 0.5),    'sleep_debt')
daily_steps   = ctrl.Antecedent(np.arange(0, 20001, 100), 'daily_steps')
screen_night  = ctrl.Antecedent(np.arange(0, 481, 1),     'screen_night')

# ── Consecuentes ─────────────────────────────────────────────────────
hrv_index = ctrl.Consequent(np.arange(0, 1.01, 0.01), 'hrv_index')
hr_stress = ctrl.Consequent(np.arange(0, 1.01, 0.01), 'hr_stress')

# ── Funciones de pertenencia (sleep_quality) ─────────────────────────
sleep_quality['poor'] = fuzz.trapmf(sleep_quality.universe, [0, 0, 2, 5])
sleep_quality['fair'] = fuzz.trapmf(sleep_quality.universe, [3, 5, 6, 8])
sleep_quality['good'] = fuzz.trapmf(sleep_quality.universe, [6, 8, 10, 10])

# ── Funciones de pertenencia (daily_steps) ───────────────────────────
daily_steps['very_sedentary'] = fuzz.trapmf(daily_steps.universe, [0, 0, 2000, 3500])
daily_steps['sedentary']      = fuzz.trapmf(daily_steps.universe, [2500, 4000, 5000, 6500])
daily_steps['active']         = fuzz.trapmf(daily_steps.universe, [5000, 7000, 8000, 10000])
daily_steps['very_active']    = fuzz.trapmf(daily_steps.universe, [9000, 11000, 20000, 20000])

# ── Reglas (selección) ───────────────────────────────────────────────
rule1  = ctrl.Rule(sleep_quality['poor'] & daily_steps['very_sedentary'],
                   hrv_index['very_low'])
rule5  = ctrl.Rule(sleep_quality['good'] & daily_steps['very_active'],
                   hrv_index['high'])
rule15 = ctrl.Rule(sleep_quality['poor'] & daily_steps['very_sedentary'] &
                   screen_night['excessive'] & sleep_debt['high'],
                   (hrv_index['very_low'], hr_stress['very_elevated']))

# ── Función de inferencia ────────────────────────────────────────────
def infer_biometrics(sleep_q, sleep_d, steps, screen_n):
    sim = ctrl.ControlSystemSimulation(
        ctrl.ControlSystem([rule1, rule5, rule15, ...])
    )
    sim.input['sleep_quality'] = np.clip(sleep_q, 0, 10)
    sim.input['sleep_debt']    = np.clip(sleep_d, 0, 72)
    sim.input['daily_steps']   = np.clip(steps,   0, 20000)
    sim.input['screen_night']  = np.clip(screen_n, 0, 480)
    sim.compute()

    hrv    = sim.output['hrv_index']
    stress = sim.output['hr_stress']

    return {
        'hrv_index': round(hrv, 3),
        'hrv_label': "muy baja" if hrv < 0.25 else
                     "baja"     if hrv < 0.50 else
                     "normal"   if hrv < 0.75 else "alta",
        'hr_stress': round(stress, 3),
        'hr_stress_label': "relajado"           if stress < 0.25 else
                           "ligeramente activo" if stress < 0.50 else
                           "elevado"            if stress < 0.75 else "muy elevado"
    }
```

### Integración con el modelo GBT

```python
def enrich_globem_features(df: pd.DataFrame) -> pd.DataFrame:
    results = df.apply(lambda row: infer_biometrics(
        sleep_q  = row['sleep_quality_normalized'],
        sleep_d  = row['sleep_debt_hours'],
        steps    = row['f_steps:fitbit_steps_rapids_sumsteps:allday'],
        screen_n = row['f_screen:phone_screen_rapids_sumdurationunlock:night']
    ), axis=1)

    df['hrv_index_fuzzy'] = [r['hrv_index'] for r in results]
    df['hr_stress_fuzzy'] = [r['hr_stress'] for r in results]

    # Feature de interacción → top-3 SHAP esperado
    df['bio_digital_risk'] = (
        df['hr_stress_fuzzy'] *
        (1 - df['hrv_index_fuzzy']) *
        df['session_duration_norm']
    )
    return df
```

### Limitaciones y mitigaciones

| Limitación | Evidencia | Mitigación |
|---|---|---|
| HRV-sedentarismo directo: efecto débil | IJERPH 2021: β=0.24 bpm/h, no clínicamente significativo aislado | Se modela como cadena causal (sedentarismo → simpático → HR elevada → HRV reducida), no correlación directa |
| Variabilidad individual alta | Kim et al. 2018: HRV afectada por genética y temporada | Normalización por baseline personal en features de GLOBEM (`_norm`) |
| GLOBEM sin HR directa | Dataset de fitness tracker, no clínico | El proxy es feature del GBT, no sustituto clínico. En producción, el watch da la señal real |
| Sistema borroso sin aprendizaje | Reglas fijas basadas en literatura | Los pesos se pueden calibrar con datos de GLOBEM mediante ANFIS |

---

## 🤖 Capa 2: LightGBM + SHAP

### ¿Por qué Gradient Boosting Trees?

- **Explicabilidad nativa** mediante SHAP values — cada predicción tiene una razón
- **Robusto con datos tabulares** de esta naturaleza
- **No requiere millones de datos** — funciona bien con histórico de semanas
- **Personalizable** — se puede fine-tunear por usuario con pocas observaciones

### Target variable

```python
optimal_stop_now = 1  # si en los próximos 15 minutos se registra:
                      #   - caída de HRV > 15% adicional, O
                      #   - inicio de patrón de scroll compulsivo, O
                      #   - score de bienestar semanal bajo + uso nocturno elevado
                  0   # en caso contrario
```

### Pipeline completo

```python
# 1. Carga y preprocesamiento
df = load_globem(['screen', 'steps', 'sleep', 'dep_weekly'])
df = segment_by_time_window(df, windows=[5, 15, 30])  # minutos

# 2. Feature engineering
df['bio_digital_divergence'] = df['hr_above_baseline'] * df['session_duration']
df['compulsion_score']       = df['unlock_frequency'] / df['session_duration']
df['recovery_debt_index']    = df['sleep_debt'] + df['movement_gap'] - df['hrv_delta']
df['night_bio_risk']         = df['is_night'] * df['hr_elevated'] * df['session_duration']

# 3. Capa 1: inferencia borrosa de variables latentes
df = enrich_globem_features(df)   # añade hrv_index_fuzzy, hr_stress_fuzzy, bio_digital_risk

# 4. Modelo principal
model = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05)
model.fit(X_train, y_train)

# 5. Explicabilidad
explainer  = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X)
```

### Explicabilidad en el watch

Cuando el modelo decide intervenir, el usuario recibe en su muñeca las **3 razones principales** en lenguaje natural:

```
🟡 "Buen momento para un descanso"

↑ Llevas 42 min sin moverte
↑ Tu ritmo cardíaco subió un 22%
🌙 Son las 23:15 y llevas 90 min de pantalla
```

---

## 📱 Producto: Flujo de usuario

```
1. ONBOARDING (semana 1)
   └── El modelo aprende tu baseline personal
       (HR en reposo, HRV típica, patrones de sueño, horarios)

2. DETECCIÓN PASIVA
   └── WristGuard recoge datos en segundo plano
       sin que el usuario haga nada

3. INTERVENCIÓN INTELIGENTE
   └── Vibración suave en el watch
   └── Mensaje con las 3 razones principales (SHAP)
   └── Sugerencia, nunca bloqueo forzado

4. FEEDBACK DEL USUARIO
   └── "¿Era buen momento?" → el modelo aprende y mejora
   └── Reinforcement learning ligero sobre preferencias personales

5. DASHBOARD SEMANAL
   └── Score de bienestar digital
   └── Tus mejores y peores momentos de la semana
   └── Tendencias de tus métricas biométricas
```

---

## 🎯 Usuario objetivo

**Perfil principal:**
- 18-35 años, con smartwatch (Apple Watch, Galaxy Watch, Garmin, Fitbit)
- Consciente de que usa demasiado el móvil
- Le importa su salud y bienestar — ya usa apps de fitness o meditación
- Orientado a la optimización personal ("quantified self")

**Por qué este perfil:**
- Ya tiene el hardware necesario (smartwatch)
- Ya está en el mindset de medir para mejorar
- La propuesta de valor resuena inmediatamente: no es control parental, es autoconocimiento

**Lo que NO somos:**
- No somos una app de control parental
- No bloqueamos el móvil a la fuerza
- No juzgamos el tiempo de pantalla — juzgamos **cómo responde tu cuerpo**

---

## 🔄 El aprendizaje continuo

WristGuard mejora con el tiempo de dos formas:

**1. Personalización individual:**  
Cada usuario refina su propio modelo con su feedback. Después de 2-3 semanas, las intervenciones son notablemente más precisas que al principio.

**2. Mejora del modelo global:**  
Los patrones anonimizados de todos los usuarios (con consentimiento explícito) alimentan mejoras al modelo base. El sistema aprende qué combinaciones biométricas predicen mejor el momento óptimo para distintos perfiles de usuario.

---

## 🚀 Stack tecnológico

| Componente | Tecnología |
|---|---|
| Inferencia borrosa | scikit-fuzzy (Mamdani) |
| Modelo ML | LightGBM + SHAP |
| Backend | FastAPI (Python) |
| App móvil | React Native |
| App watch | WatchOS / Wear OS nativo |
| Datos biométricos | Apple HealthKit / Google Health Connect |
| Datos de pantalla | Screen Time API (iOS) / Digital Wellbeing API (Android) |
| Infraestructura | Cloud con procesamiento on-device para privacidad |

---

## 🔐 Privacidad por diseño

Los datos biométricos son altamente sensibles. WristGuard se construye con **Privacy by Design**:

- El modelo de inferencia se ejecuta **on-device** siempre que es posible
- Los datos en crudo nunca salen del dispositivo sin cifrado de extremo a extremo
- El usuario puede exportar, ver y eliminar todos sus datos en cualquier momento
- Cumplimiento con **GDPR** (Europa) y regulaciones equivalentes
- Los datos anonimizados para mejora del modelo requieren **opt-in explícito**

---

## 📋 Plan para el Hackathon

### Día 1: Datos y modelo base
- [ ] Descargar y explorar GLOBEM (PhysioNet)
- [ ] Feature engineering sobre `screen.csv`, `steps.csv`, `sleep.csv`
- [ ] Definir y construir el target variable desde `dep_weekly.csv`
- [ ] Entrenar modelo LightGBM baseline
- [ ] Generar SHAP values y validar explicabilidad

### Día 2: Inferencia borrosa y validación
- [ ] Implementar sistema Mamdani con `scikit-fuzzy`
- [ ] Calibrar funciones de pertenencia con distribuciones reales de GLOBEM
- [ ] Integrar `hrv_index_fuzzy`, `hr_stress_fuzzy` y `bio_digital_risk` en el pipeline
- [ ] Validar con cross-validation por usuario (LOSO — Leave-One-Subject-Out)
- [ ] Construir demo de intervención con explicación en lenguaje natural

### Día 3: Producto y pitch
- [ ] Mockup del watch con la notificación explicable
- [ ] Dashboard de bienestar digital (Streamlit o React)
- [ ] Preparar las métricas del modelo para el pitch
- [ ] Ensayar demostración en vivo

### Métricas de éxito para el último día

```
Modelo:
  - AUC-ROC > 0.75 en validación cruzada
  - bio_digital_risk en top-3 SHAP features
  - Top 3 SHAP features con sentido clínico y biológico
  - Diferencia significativa entre grupos de alto/bajo riesgo

Inferencia borrosa:
  - hrv_index y hr_stress coherentes con los ejemplos clínicos documentados
  - R15 ("tormenta perfecta") activándose en los casos esperados

Producto:
  - Demo funcional del flujo de intervención
  - Explicación clara de por qué no es "otro timer de pantalla"
  - Story: from data → fuzzy inference → GBT insight → action → feedback loop
```

---

## 📚 Referencias y validación científica

### Machine Learning y datos
- **GLOBEM Dataset** — UW EXP Lab, PhysioNet (2022). Multi-year mobile and wearable sensing datasets.
- **WESAD** — Schmidt et al. (2018). Wearable Stress and Affect Detection. ACM ICMI.

### HRV, sueño y actividad física
- **HRV-Sueño:** *Heart Rate Variability, Sleep Quality and Physical Activity in Medical Students*. ScienceDirect, 2024. Correlación PSQI-SDNN estadísticamente significativa.
- **RMSSD-Bienestar:** *Associations Between Daily HRV and Self-Reported Wellness*. MDPI Sensors, 2025. β=0.510 (sleep), 0.281 (fatiga), 0.353 (estrés).
- **HRV-Sueño profundo:** *Pre-sleep HRV predicts chronic insomnia*. Frontiers in Physiology, 2025.
- **Ejercicio-HRV:** *Interaction between exercise and sleep with HRV*. European Journal of Applied Physiology, 2025.
- **Umbrales clínicos HRV:** *Impact of exhaustive exercise on ANS*. Frontiers in Physiology, 2024. SDNN<50ms = simpático elevado; RMSSD<25ms = inhibición vagal.
- **Sedentarismo-HR:** *Associations of Sedentary Time with HR and HRV: Meta-analysis*. MDPI IJERPH, 2021. β=0.24 bpm/hora sedentaria.
- **Sedentarismo-Simpático:** *Sedentary Lifestyle: Updated Evidence*. PMC, 2020.
- **Estrés-Sedentarismo:** *Sedentary Behaviour and Psychobiological Stress Reactivity*. Neuroscience & Biobehavioral Reviews, 2022.
- **Sueño combinado:** *Combined effect of poor sleep and low HRV on metabolic syndrome*. Sleep Journal, 2023. MIDUS II, n=966.

### Lógica borrosa para estrés fisiológico
- **Sierra et al. (2011).** *A Stress-Detection System Based on Physiological Signals and Fuzzy Logic*. IEEE Trans. Ind. Electron.
- **Zalabarria et al. (2020).** *A low-cost portable solution for stress estimation based on real-time fuzzy algorithm*. IEEE Access 8: 74118–74128.
- **Springer (2023).** *State-of-the-Art of Stress Prediction from HRV Using AI*. Cognitive Computation. Revisión de 43 estudios.
- **AIMS Neuroscience (2024).** *Predicting Stress Using Physiological Data*. Revisión de clasificadores (fuzzy, SVM, ANN, Bayesian).

### Uso nocturno y sueño
- **Lemola et al. (2015).** *Adolescents' Electronic Media Use at Night*. PLOS ONE.
- **Shaffer & Ginsberg (2017).** *An Overview of HRV Metrics and Norms*. Frontiers in Public Health.

---

## 👥 El equipo

*[Añadir nombres y roles del equipo aquí]*

---

## 📄 Licencia

MIT License — ver `LICENSE` para más detalles.

---

<div align="center">

**WristGuard** — *Porque tu cuerpo merece una segunda opinión.*

⌚ + 📱 + 🧠 = 🌿

</div>
