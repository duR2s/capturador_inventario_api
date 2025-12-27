# [capturador_inventario_api]

![Badge de Estado](https://img.shields.io/badge/Estado-En_Desarrollo-yellow)
![Badge de Version](https://img.shields.io/badge/Version-1.0.0-blue)
**[capturador_inventario_api]** es una API RESTful diseñada para facilitar la captura de inventarios fisicos en sistemas microsip, proporcionando datos de la bd microsip (firebird) hacia esta API rest.

Este backend sirve como núcleo para aplicaciones web y móviles, encargándose de la autenticación, procesamiento de datos en existencias de articulos, sincronizacion con la bd microsip y gestion de usuarios basica.

## 📋 Tabla de Contenidos

1. [Tecnologías](#-tecnologías)
2. [Prerrequisitos](#-prerrequisitos)
3. [Instalación y Configuración](#-instalación-y-configuración)
4. [Ejecución](#-ejecución)
5. [Documentación de la API](#-documentación-de-la-api)
6. [Testing](#-testing)
7. [Estructura del Proyecto](#-estructura-del-proyecto)

---

## 🛠 Tecnologías

Este proyecto está construido con:

* **Lenguaje:** Python 3.12.10 (32-bit) /  Node.js v18.20.8.
* **Framework:**  Django 5.0.2
* **Base de Datos:** 10.4.32 MariaDB

---

## 📦 Prerrequisitos

Asegúrate de tener instalado:

### Sistema y Herramientas Básicas
* **Sistema Operativo:** Windows 10/11 (Recomendado para integración nativa con Microsip).
* **[Git](https://git-scm.com/):** Para el control de versiones.
* **[Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/):** Necesario para compilar ciertas librerías de Python (como `mysqlclient`).

### Runtimes y Lenguajes
* **[Python 3.12.x (32-bit)](https://www.python.org/downloads/windows/):**
    * ⚠️ **Importante:** Debes instalar la versión **32-bit** (x86), *no* la de 64-bit (x64).
    * *Razón:* Las librerías `fbclient.dll` de Microsip suelen ser de 32 bits. Python de 64 bits no puede cargar DLLs de 32 bits.
* **[Node.js v18 LTS](https://nodejs.org/)** (Opcional, si se requiere para scripts de frontend/tooling).

### Bases de Datos
1.  **MariaDB (Local):**
    * Versión 10.4 o superior (Compatible con XAMPP).
    * Debes tener un usuario con privilegios para crear la base de datos del API.
2.  **Drivers de Firebird (Microsip):**
    * Es necesario tener las librerías cliente de Firebird instaladas o accesibles en el PATH del sistema (`fbclient.dll` o `gds32.dll`).
    * *Generalmente, si tienes Microsip instalado en la máquina de desarrollo, esto ya está cubierto.*
2.  **Api Microsip (Microsip):**
    * Es necesario tener la API de Microsip descargada(`ApiMicrosip.dll`).
    * *Descargarla desde du sitio: https://soporte.microsip.com/.*
---

## 🚀 Instalación y Configuración

Sigue estos pasos para levantar el entorno de desarrollo localmente:

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/duR2s/capturador_inventario_api.git
    cd nombre-del-repo
    ```
    
2.  **Configurar Variables de Entorno:**
    Crea una carpeta para el enviroment en la raíz root/venv.

3.  **Instalar Dependencias (Modo Nativo):**
    ```bash
    python -m venv venv
    source venv/Scripts/activate  # En Windows: venv\Scripts\activate
    pip install -r requirements-base.txt
    # Si causa problemas, intenta con: pip install -r requirements.txt

4. **Copiar los dll a la raiz del venv:**
    Copiar los archivos 'ApiMicrosip.dll' y 'fdbclient.dll' a la raíz del entorno virtual.

---

## ▶️ Ejecución

Levanta la base de datos y el servidor:

    ```bash
    #Con el venv activado 
    cd /ruta/nombreDeProyecto
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver
    ```
---

## 🌳 Estructura

capturador_inventario_api/
├── capturador_inventario_api/      # Núcleo del Backend
│   ├── microsip_api/               # Módulo de integración con ERP Microsip
│   │   ├── microsip_api.py         # Conversión de tipos Ctypes a Python
│   │   └── ...connection.py        # Manejo de conexión a DLLs
│   ├── views/                      # Endpoints organizados por dominio
│   │   ├── auth.py                 # JWT y Autenticación
│   │   ├── capturaInventario.py    # Lógica de conteo físico
│   │   └── ...
│   ├── models.py                   # Definición de tablas (Inventarios, Artículos)
│   ├── serializers.py              # Transformación de datos para la API
│   ├── tasks.py                    # Tareas asíncronas (Sincronización BD)
│   └── settings.py                 # Configuración de Django
│
├── static/                         # Archivos estáticos
├── my.cnf                          # Configuración BD (No incluido en repo)
├── manage.py                       # CLI de Django
└── run_server.py                   # Script de entrada para servidor productivo (Waitress/Gunicorn)


---

## 🌊 Flujo de Trabajo

flowchart TD
    %% Estilos
    classDef endpoint fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef decision fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px;
    classDef success fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef db fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;

    Client[💻 Cliente Frontend] --> Auth{🔑 ¿Autenticado?}
    Auth -- No --> Resp401[🛑 401 Unauthorized]:::error
    Auth -- Sí --> Router((📡 Router))

    %% --- BLOQUE: CAPTURAS (HEADERS) ---
    subgraph G_CAPTURA [📦 Gestión de Capturas (Cabeceras)]
        direction TB
        Router --> GET_CAPT[GET /captura/]:::endpoint
        GET_CAPT --> RoleCheck{👮 ¿Es Admin?}:::decision
        RoleCheck -- Sí --> QueryAll[(All Capturas)]:::db
        RoleCheck -- No --> QueryUser[(User Capturas)]:::db
        QueryAll & QueryUser --> Resp200L[✅ 200 Lista]:::success

        Router --> POST_CAPT[POST /captura/]:::endpoint
        POST_CAPT --> ValC{Validar}:::decision
        ValC -- OK --> TxC[💾 Transaction Save]:::db --> Resp201C[✅ 201 Created]:::success
        ValC -- Error --> Resp400C[⚠️ 400 Bad Request]:::error

        Router --> PATCH_CAPT[PATCH /captura/:id]:::endpoint
        PATCH_CAPT --> OwnerP{¿Permiso?}:::decision
        OwnerP -- OK --> ChkEst{¿Cambia Estado?}:::decision
        ChkEst -- "Si & !Admin" --> Resp403E[🚫 403 Forbidden]:::error
        ChkEst -- OK --> SaveP[💾 Save]:::db --> Resp200P[✅ 200 OK]:::success
    end

    %% --- BLOQUE: DETALLES Y PRODUCTOS ---
    subgraph G_DETALLE [📄 Detalles y Productos]
        direction TB
        Router --> BUSCAR[GET /buscar-articulo/]:::endpoint
        BUSCAR --> FindA{¿Existe Clave?}:::decision
        FindA -- Sí --> GetEx[🔍 Obtener Existencia]:::db --> Resp200Art[✅ 200 Datos Articulo]:::success
        FindA -- No --> Resp404A[🤷 404 Not Found]:::error

        Router --> POST_DET[POST /detalle/]:::endpoint
        POST_DET --> ValD{Validar}:::decision
        ValD -- OK --> SaveD[💾 Save Detalle]:::db --> Resp201D[✅ 201 Created]:::success

        Router --> SYNC[POST /sync/]:::endpoint
        SYNC --> ValS{Validar Lista}:::decision
        ValS -- OK --> TxSync[⚡ Atomic Bulk Save]:::db --> Resp200S[✅ 200 Synced]:::success
    end

    %% --- BLOQUE: TICKETS (INCIDENCIAS) ---
    subgraph G_TICKET [🎫 Tickets e Incidencias]
        Router --> TICKET[POST /ticket/]:::endpoint
        TICKET --> ValT{Validar}:::decision
        ValT -- OK --> ChkQ{¿Cant <= Contada?}:::decision
        ChkQ -- No --> Resp400TQ[⚠️ 400 Exceso]:::error
        ChkQ -- Sí --> TxT[📉 Restar Cant + 💾 Crear Ticket]:::db --> Resp201T[✅ 201 Created]:::success
    end

    %% --- BLOQUE: UTILIDADES ---
    subgraph G_UTILS [⚙️ Utilidades]
        Router --> EXPORT[GET /excel/]:::endpoint
        EXPORT --> GenXLS[📊 Generar XLSX] --> RespFile[📁 File Download]:::success
    end