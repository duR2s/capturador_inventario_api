from waitress import serve
# Asegúrate que 'capturador_inventario_api' sea el nombre de la carpeta que contiene wsgi.py
from capturador_inventario_api.wsgi import application 

if __name__ == '__main__':
    print("--- INICIANDO SERVIDOR DE APLICACIÓN (WAITRESS) ---")
    print("Escuchando internamente en 127.0.0.1:8080")
    print("Recuerda iniciar Nginx para recibir tráfico externo.")

    serve(
        application, 
        host='127.0.0.1', # Solo acepta tráfico de Nginx (localhost)
        port=8080,
        threads=1         # CRUCIAL: 1 hilo para evitar conflictos con la DLL de Microsip
    )