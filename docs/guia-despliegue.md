# Guía de despliegue de AgroSismo (PythonAnywhere)

Antes de empezar: en PythonAnywhere el plan gratis de cuentas nuevas **no incluye MySQL** y la app gratis **expira al mes**. Para MySQL usa un plan de pago (el básico, "Hacker"; confirma el precio en pythonanywhere.com/pricing). Con el plan gratis puedes publicar con SQLite (solo para la sustentación).

## 1. Subir el código
1. Crea la cuenta en pythonanywhere.com. Tu usuario será `USUARIO`.
2. Sube el proyecto a GitHub (sin `.env`, `db.sqlite3` ni `media/`; el `.gitignore` ya los excluye).
3. En PythonAnywhere, pestaña **Consoles → Bash**:
   ```
   git clone https://github.com/TU_USUARIO/TU_REPO.git agrosismo
   cd agrosismo
   python3.13 -m venv ~/venv-agrosismo     # usa la versión de Python más alta que ofrezca (mínimo 3.10)
   source ~/venv-agrosismo/bin/activate
   pip install -r requirements.txt
   ```
   Si `mysqlclient` falla y usas SQLite, instala lo demás con `pip install Django Pillow reportlab`.

## 2. Base de datos
- **Con MySQL (plan de pago):** pestaña **Databases**, pon una contraseña fuerte y crea la base `USUARIO$agrosismo`. El servidor es `USUARIO.mysql.pythonanywhere-services.com`.
- **Con SQLite (gratis):** no definas `DB_NAME`.

## 3. Archivo .env
En la consola, dentro de `~/agrosismo`:
```
nano .env
```
Pega (cambia los valores):
```
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=PEGA_AQUI_LA_CLAVE
DJANGO_ALLOWED_HOSTS=USUARIO.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://USUARIO.pythonanywhere.com
DB_NAME=USUARIO$agrosismo
DB_USER=USUARIO
DB_PASSWORD=TU_CLAVE_MYSQL
DB_HOST=USUARIO.mysql.pythonanywhere-services.com
DB_PORT=3306
```
(Con SQLite borra las 5 líneas que empiezan con DB_.)

Para generar la SECRET_KEY:
```
python -c "import secrets; print(secrets.token_urlsafe(60))"
```

## 4. Preparar la aplicación
```
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser        # será el desarrollador
python manage.py check --deploy
```

## 5. Web app
1. Pestaña **Web → Add a new web app → Manual configuration**, con la misma versión de Python del venv.
2. **Virtualenv:** `/home/USUARIO/venv-agrosismo`
3. **Source code:** `/home/USUARIO/agrosismo`
4. Abre el archivo WSGI y déjalo así:
   ```python
   import os, sys
   sys.path.insert(0, "/home/USUARIO/agrosismo")
   os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
5. **Static files:** URL `/static/` → carpeta `/home/USUARIO/agrosismo/staticfiles`.
   **No** crees una entrada para `/media/`: las fotos son privadas y las entrega el sistema.
6. Activa **Force HTTPS** y pulsa **Reload**.

## 6. Pruebas después de publicar
1. Abre `https://USUARIO.pythonanywhere.com`, entra y crea una finca y un administrador.
2. Instala la app desde el celular con el menú del navegador ("Instalar" / "Añadir a pantalla de inicio").
3. Con el celular en modo avión, haz un registro rápido; al volver la señal debe sincronizar.
4. Sube una foto y descarga un PDF.

## 7. Actualizar después
```
cd ~/agrosismo && git pull
source ~/venv-agrosismo/bin/activate
python manage.py migrate && python manage.py collectstatic --noinput
```
y **Reload** en la pestaña Web.

## 8. Copias de seguridad
- MySQL: `mysqldump -u USUARIO -h USUARIO.mysql.pythonanywhere-services.com 'USUARIO$agrosismo' > copia.sql`
- Fotos: copiar la carpeta `media/`. Guarda las copias fuera del servidor.
- Hazlas al menos cada semana.
