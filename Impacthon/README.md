# Proyecto Teyka: Medimos tus constantes, te enseñamos cuándo parar

> "De la biometría pasiva a la intervención proactiva."

Proyecto Teyka es una solución tecnológica diseñada para combatir la pérdida de autorregulación cognitiva mediante el análisis de datos biométricos en tiempo real. A diferencia del bloqueo reactivo tradicional, Teyka actúa como un monitor continuo que detecta la saturación del sistema nervioso autónomo para sugerir desvíos psicológicos de bajo coste basados en IA.

---

## Cómo ejecutar el proyecto

```bash
cd gem
python -m http.server 8096
# Abrir en el navegador el dashboard de desarrolladores: http://localhost:8096/admin.html
```
[http://localhost:8096/admin.html](http://localhost:8096/admin.html)
```bash
cd "gem - phone"
python -m http.server 8097
# Abrir en el navegador la app móvil: http://localhost:8097/mobile.html
# Presionar Shift + o para ejecutar el Onboarding de la APP.
```
[http://localhost:8097/mobile.html](http://localhost:8097/mobile.html)

---

## Arquitectura del Producto

El proyecto se divide en tres productos integrados en este repositorio:

1. **Dashboard de Presentación (Frontend Web)**
   - **Ruta:** `gem/index.html`
   - **Propósito:** Panel visual de alto nivel que exhibe los fundamentos biométricos en tiempo real, ideal para la comprensión inmediata del jurado.
2. **Panel de Administración e Investigación**
   - **Ruta:** `gem/admin.html`
   - **Propósito:** Interfaz analítica para investigadores. Permite observar las correlaciones de Pearson, los algoritmos de backtesting profundo, la base de datos de usuarios y exportar métricas en crudo.
3. **Aplicación Móvil (Simulador de Usuario Final)**
   - **Ruta:** `gem - phone/mobile.html`
   - **Propósito:** Prototipo funcional que el usuario experimenta. Monitoriza el Índice de Saturación (IS) intradía en tiempo real y ejecuta intervenciones proactivas generadas dinámicamente mediante el ecosistema Gemini de Inteligencia Artificial.

---

## Fundamentos Científicos

La validez técnica de Teyka se apoya sistemáticamente en el ecosistema de investigación **GLOBEM** y estudios longitudinales recientes.

> Wang, W., et al. (2021). "Social Sensing: Predicting Well-being from Heart Rate Variability and Smartphone Sensing Data in the Wild."

La evidencia demuestra que una disminución acentuada en el marcador **RMSSD (Root Mean Square of Successive Differences)** precede consistentemente a los episodios de baja autorregulación, facilitando ciclos de uso prolongado de pantallas por inercia. Teyka combina la Variabilidad de la Frecuencia Cardíaca (HRV) y logs de acelerometría y pantalla para identificar estos contextos anómalos.

---

## El Índice de Saturación (IS)

El núcleo algorítmico del proyecto reside en el cálculo en tiempo real del Índice de Saturación (IS). Este KPI unificado permite evaluar la vulnerabilidad cognitiva del usuario integrando su biometría y su comportamiento.

El sistema pondera estas divergencias respecto al marco base (baseline) individual del usuario:
- Desviación fisiológica derivada de intervalos R-R.
- Entropía computacional obtenida a través de la frecuencia de interacciones con el dispositivo en tiempos o fragmentos considerados de inactividad biológica.

---

## Stack Tecnológico

* **Procesamiento y Extracción (ETL):** Python (Pandas, NumPy)
* **Visualización Dinámica:** HTML5, CSS3 Avanzado, Vanilla JavaScript, Chart.js
* **Motor Cognitivo (Nudges):** Google Gemini Pro / Flash AI 
* **Data Mining:** Datasets Fitbit Fitabase (Kaggle) y el estudio longitudinal GLOBEM (University of Washington).

---

> Proyecto Teyka - Impacthon USC 2026
