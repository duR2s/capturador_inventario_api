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

* **Lenguaje:** Python Python 3.12.10 (32-bit) /  Node.js v18.20.8.
* **Framework:**  Django 5.0.2
* **Base de Datos:** 10.4.32 MariaDB
//* **Cache:** [Ej. Redis] (Opcional)
//* **Contenedores:** Docker & Docker Compose

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

---

## 🚀 Instalación y Configuración

Sigue estos pasos para levantar el entorno de desarrollo localmente:

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/duR2s/capturador_inventario_api.git
    cd nombre-del-repo
    ```

2.  **Configurar Variables de Entorno:**
    Crea un archivo `.env` en la raíz basado en el ejemplo proporcionado.
    ```bash
    cp .env.example .env
    ```
    > **Nota:** Asegúrate de actualizar las credenciales de base de datos en el archivo `.env` si no usas los valores por defecto.

3.  **Instalar Dependencias (Modo Nativo):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

---

## ▶️ Ejecución

Levanta la base de datos y el servidor:

```bash
#Con el venv activado 
cd /ruta/nombreDeProyecto
python manage.py migrate
python manage.py runserver