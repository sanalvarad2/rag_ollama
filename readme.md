# Proyecto Python con Virtual Environment

Este documento describe los pasos necesarios para configurar un entorno virtual, instalar las dependencias y ejecutar la aplicación.

## Requisitos previos

- Python 3.7 o superior instalado.
- `pip` instalado (viene con Python).
- Qdrant instalado para la gestión de vectores. [Docker](https://qdrant.tech/documentation/quickstart/).
- Ollama instalado para la integración con modelos de lenguaje.

## Pasos para configurar el entorno

### 1. Crear un entorno virtual

Ejecuta el siguiente comando para crear un entorno virtual en el directorio `venv`:

```bash
python -m venv venv
```

### 2. Activar el entorno virtual

- En **Windows**:

    ```bash
    venv\Scripts\activate
    ```

- En **macOS/Linux**:

    ```bash
    source venv/bin/activate
    ```

### 3. Instalar las dependencias

Con el entorno virtual activado, instala las dependencias desde el archivo `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación

Ejecuta la aplicación con `uvicorn`:

```bash
uvicorn main:app --reload
```

La aplicación estará disponible en `http://127.0.0.1:8000`.

## Notas adicionales

- Usa `deactivate` para salir del entorno virtual.
- Asegúrate de que el archivo `requirements.txt` esté actualizado con las dependencias necesarias.
