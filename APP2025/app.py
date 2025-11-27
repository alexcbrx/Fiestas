from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_mysqldb import MySQL
import os
import uuid
import requests
import io
import MySQLdb
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# -------------------- CONFIGURACIÓN MYSQL --------------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'XcuberoX'
app.config['MYSQL_DB'] = 'fiestas'

# Carpeta para fotos de perfil y servicios (asegúrate de crearla)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads', 'servicios')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

mysql = MySQL(app)

# -------------------- HELPERS DE IMÁGENES --------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file_storage):
    """Guarda archivo subido por formulario y devuelve la ruta relativa (ej: /static/uploads/servicios/uuid.jpg)"""
    if not file_storage or file_storage.filename == '':
        return None
    if not allowed_file(file_storage.filename):
        return None
    filename = secure_filename(file_storage.filename)
    unique = f"{uuid.uuid4().hex}_{filename}"
    path = os.path.join(app.config['UPLOAD_FOLDER'], unique)
    file_storage.save(path)
    return '/' + path.replace('\\', '/')

def save_image_from_url(url):
    """Descarga imagen desde URL y la guarda, devuelve ruta relativa o None."""
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get('Content-Type', '')
        if 'image' not in content_type:
            return None
        ext = content_type.split('/')[-1].split(';')[0]
        if ext not in ALLOWED_EXTENSIONS:
            ext = 'jpg'
        unique = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(app.config['UPLOAD_FOLDER'], unique)
        with open(path, 'wb') as f:
            f.write(resp.content)
        return '/' + path.replace('\\', '/')
    except Exception as e:
        print("Error saving image from url:", e)
        return None

# -------------------- LOGIN --------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'usuario' in request.form and 'contraseña' in request.form:
        usuario = request.form['usuario']
        contraseña = request.form['contraseña']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM usuarios WHERE usuario = %s AND contraseña = %s', (usuario, contraseña,))
        cuenta = cursor.fetchone()
        cursor.close()
        if cuenta:
            session['loggedin'] = True
            session['id'] = cuenta['id']
            session['usuario'] = cuenta['usuario']
            return redirect(url_for('inicio'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

# -------------------- REGISTRO --------------------
@app.route('/registro', methods=['POST'])
def registro():
    if request.method == 'POST' and 'usuario' in request.form and 'contraseña' in request.form and 'correo' in request.form:
        usuario = request.form['usuario']
        contraseña = request.form['contraseña']
        correo = request.form['correo']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM usuarios WHERE usuario = %s', (usuario,))
        cuenta = cursor.fetchone()
        if cuenta:
            flash('El usuario ya existe', 'warning')
            cursor.close()
            return redirect(url_for('login'))
        if not re.match(r'[^@]+@[^@]+\.[^@]+', correo):
            flash('Correo inválido', 'warning')
            cursor.close()
            return redirect(url_for('login'))
        cursor.execute('INSERT INTO usuarios (usuario, correo, contraseña) VALUES (%s, %s, %s)', (usuario, correo, contraseña))
        mysql.connection.commit()
        cursor.close()
        flash('Registro exitoso', 'success')
        return redirect(url_for('login'))
    return redirect(url_for('login'))

# -------------------- INICIO --------------------
@app.route('/inicio')
def inicio():
    if 'loggedin' in session:
        return render_template('inicio.html', usuario=session['usuario'])
    return redirect(url_for('login'))

# -------------------- PERFIL --------------------
@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Obtener todas las fiestas del usuario
    cursor.execute('''
        SELECT f.id, f.nombre AS fiesta_nombre, f.tipo,
               c.nombre AS comida_nombre,
               s.nombre AS salon_nombre,
               d.nombre AS dj_nombre,
               e.nombre AS entretenimiento_nombre,
               f.invitados
        FROM fiestas f
        LEFT JOIN comidas c ON f.comida_id = c.id
        LEFT JOIN salones s ON f.salon_id = s.id
        LEFT JOIN djs d ON f.dj_id = d.id
        LEFT JOIN entretenimientos e ON f.entretenimiento_id = e.id
        WHERE f.usuario_id = %s
    ''', (session['id'],))
    fiestas = cursor.fetchall()

    # Obtener datos para los dropdowns
    cursor.execute('SELECT * FROM salones')
    salones = cursor.fetchall()
    cursor.execute('SELECT * FROM comidas')
    comidas = cursor.fetchall()
    cursor.execute('SELECT * FROM djs')
    djs = cursor.fetchall()
    cursor.execute('SELECT * FROM entretenimientos')
    entretenimientos = cursor.fetchall()

    cursor.close()
    return render_template('perfil.html', fiestas=fiestas, salones=salones, comidas=comidas, djs=djs, entretenimientos=entretenimientos)
# -------------------- CREAR FIESTA --------------------
@app.route('/crear_fiesta', methods=['POST'])
def crear_fiesta():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    nombre = request.form['nombre']
    tipo = request.form['tipo']
    ubicacion = request.form.get('ubicacion')
    fecha = request.form.get('fecha')
    hora = request.form.get('hora')
    invitados = request.form.get('invitados')
    salon_id = request.form.get('salon') or None
    comida_id = request.form.get('comida') or None
    dj_id = request.form.get('dj') or None
    entretenimiento_id = request.form.get('entretenimiento') or None

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        INSERT INTO fiestas (nombre, tipo, ubicacion, usuario_id, salon_id, comida_id, dj_id, entretenimiento_id, fecha, hora, invitados)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (nombre, tipo, ubicacion, session['id'], salon_id, comida_id, dj_id, entretenimiento_id, fecha, hora, invitados))
    mysql.connection.commit()
    cursor.close()

    flash('🎉 Fiesta creada con éxito', 'success')
    return redirect(url_for('perfil'))


# -------------------- EDITAR FIESTA --------------------
@app.route('/editar_fiesta/<int:id>', methods=['GET', 'POST'])
def editar_fiesta(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        nombre = request.form['nombre']
        tipo = request.form['tipo']
        ubicacion = request.form.get('ubicacion')
        salon_id = request.form.get('salon') or None
        comida_id = request.form.get('comida') or None
        dj_id = request.form.get('dj') or None
        entretenimiento_id = request.form.get('entretenimiento') or None

        cursor.execute('''
            UPDATE fiestas 
            SET nombre=%s, tipo=%s, ubicacion=%s, salon_id=%s, comida_id=%s, dj_id=%s, entretenimiento_id=%s 
            WHERE id=%s AND usuario_id=%s
        ''', (nombre, tipo, ubicacion, salon_id, comida_id, dj_id, entretenimiento_id, id, session['id']))
        mysql.connection.commit()
        cursor.close()
        flash('✅ Fiesta actualizada', 'info')
        return redirect(url_for('perfil'))
    else:
        cursor.execute('''
            SELECT * FROM fiestas WHERE id=%s AND usuario_id=%s
        ''', (id, session['id']))
        fiesta = cursor.fetchone()
        cursor.execute('SELECT * FROM salones')
        salones = cursor.fetchall()
        cursor.execute('SELECT * FROM comidas')
        comidas = cursor.fetchall()
        cursor.execute('SELECT * FROM djs')
        djs = cursor.fetchall()
        cursor.execute('SELECT * FROM entretenimientos')
        entretenimientos = cursor.fetchall()
        cursor.close()

        return render_template('editar_fiesta.html', fiesta=fiesta, salones=salones, comidas=comidas, djs=djs, entretenimientos=entretenimientos)

# -------------------- ELIMINAR FIESTA --------------------
@app.route('/eliminar_fiesta/<int:id>')
def eliminar_fiesta(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM fiestas WHERE id=%s AND usuario_id=%s', (id, session['id']))
    mysql.connection.commit()
    cursor.close()
    flash('🗑️ Fiesta eliminada', 'danger')
    return redirect(url_for('perfil'))

# -------------------- SUBIR FOTO DE PERFIL --------------------
@app.route('/subir_foto', methods=['POST'])
def subir_foto():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Si el usuario sube un archivo desde el formulario
    if 'foto' in request.files and request.files['foto'].filename != '':
        file = request.files['foto']
        ruta = save_uploaded_file(file)  # usa la función que ya creaste
    else:
        # O si proporciona una URL de imagen
        url = request.form.get('foto_url')
        ruta = save_image_from_url(url) if url else None

    if not ruta:
        flash('⚠️ No se pudo guardar la imagen. Verifica el archivo o la URL.', 'warning')
        return redirect(url_for('perfil'))

    # Guarda la ruta en la base de datos
    cursor.execute('UPDATE usuarios SET foto=%s WHERE id=%s', (ruta, session['id']))
    mysql.connection.commit()
    cursor.close()

    flash('📸 Foto actualizada correctamente', 'success')
    return redirect(url_for('perfil'))


# -------------------- CERRAR SESIÓN --------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------- SERVICIOS (vista) --------------------
@app.route('/servicios')
def servicios():
    """
    Renderiza la página de servicios (tu HTML) con los servicios cargados desde la BDD.
    Mantiene tu diseño original; las secciones 'comida', 'salones', 'djs', 'entretenimiento'
    se llenan con los resultados de la base de datos.
    """
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT id, nombre, descripcion, imagen_url FROM comidas')
    comidas = cursor.fetchall()
    cursor.execute('SELECT id, nombre, descripcion, imagen_url FROM salones')
    salones = cursor.fetchall()
    cursor.execute('SELECT id, nombre, descripcion, imagen_url FROM djs')
    djs = cursor.fetchall()
    cursor.execute('SELECT id, nombre, descripcion, imagen_url FROM entretenimientos')
    entretenimientos = cursor.fetchall()
    cursor.close()
    return render_template('servicios.html', comidas=comidas, salones=salones, djs=djs, entretenimientos=entretenimientos)

# -------------------- API PARA AGREGAR SERVICIO A FIESTA --------------------
@app.route('/agregar', methods=['POST'])
def agregar_a_fiesta():
    if 'loggedin' not in session:
        return {'status': 'error', 'message': 'Debes iniciar sesión'}, 403

    data = request.get_json()
    tipo = data.get('tipo')
    item_id = data.get('id')
    fiesta_nombre = data.get('fiesta_nombre')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM fiestas WHERE nombre = %s AND usuario_id = %s", (fiesta_nombre, session['id']))
    fiesta = cursor.fetchone()

    if not fiesta:
        cursor.close()
        return {'status': 'error', 'message': 'No se encontró la fiesta o no te pertenece'}, 403

    mapa_campos = {
        'comida': 'comida_id',
        'comidas': 'comida_id',
        'dj': 'dj_id',
        'djs': 'dj_id',
        'salon': 'salon_id',
        'salones': 'salon_id',
        'entretenimiento': 'entretenimiento_id',
        'entretenimientos': 'entretenimiento_id'
    }
    campo = mapa_campos.get(tipo)
    if not campo:
        cursor.close()
        return {'status': 'error', 'message': 'Tipo de servicio inválido'}, 400

    query = f"UPDATE fiestas SET {campo} = %s WHERE id = %s"
    cursor.execute(query, (item_id, fiesta['id']))
    mysql.connection.commit()
    cursor.close()

    return {'status': 'ok', 'message': f'{tipo.capitalize()} agregado correctamente a tu fiesta \"{fiesta_nombre}\".'}

# -------------------- API PARA OBTENER LAS FIESTAS DEL USUARIO --------------------
@app.route('/mis_fiestas')
def mis_fiestas():
    if 'loggedin' not in session:
        return jsonify([])

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT nombre FROM fiestas WHERE usuario_id = %s", (session['id'],))
    fiestas = [row['nombre'] for row in cursor.fetchall()]
    cursor.close()
    return jsonify(fiestas)

# -------------------- API: LISTAR SERVICIOS (JSON) --------------------
@app.route('/api/servicios', methods=['GET'])
def listar_servicios():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    data = []
    for tipo, tabla in {
        'comida': 'comidas',
        'salones': 'salones',
        'djs': 'djs',
        'entretenimiento': 'entretenimientos'
    }.items():
        cursor.execute(f"SELECT id, nombre, descripcion, imagen_url AS imagen FROM {tabla}")
        for row in cursor.fetchall():
            row['tipo'] = tipo
            data.append(row)
    cursor.close()
    return jsonify(data)

# -------------------- API: CREAR SERVICIO (sin página admin) --------------------
@app.route('/api/servicios', methods=['POST'])
def crear_servicio_api():
    """
    Endpoint API para crear un servicio (útil si luego quieres integrar admin o usar fetch desde JS).
    Acepta JSON con: nombre, tipo, descripcion, imagen_url (opcional).
    """
    if 'loggedin' not in session:
        # permitir crear desde API si quisieras: aquí lo restringimos a sesión
        return jsonify({'status': 'error', 'message': 'No autorizado'}), 403

    data = request.get_json()
    nombre = data.get('nombre')
    tipo = data.get('tipo')
    descripcion = data.get('descripcion')
    imagen = data.get('imagen')

    tablas = {
        'comida': 'comidas',
        'salones': 'salones',
        'djs': 'djs',
        'entretenimiento': 'entretenimientos'
    }

    tabla = tablas.get(tipo)
    if not tabla:
        return jsonify({'status': 'error', 'message': 'Tipo inválido'}), 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        f"INSERT INTO {tabla} (nombre, descripcion, imagen_url) VALUES (%s, %s, %s)",
        (nombre, descripcion, imagen)
    )
    mysql.connection.commit()
    cursor.close()

    return jsonify({'status': 'ok', 'message': f'{nombre} agregado correctamente.'})

# -------------------- API: ACTUALIZAR SERVICIO --------------------
@app.route('/api/servicios/<tipo>/<int:serv_id>', methods=['PUT'])
def actualizar_servicio_api(tipo, serv_id):
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'No autorizado'}), 403

    tablas = {
        'comida': 'comidas',
        'salones': 'salones',
        'djs': 'djs',
        'entretenimiento': 'entretenimientos'
    }
    tabla = tablas.get(tipo)
    if not tabla:
        return jsonify({'status': 'error', 'message': 'Tipo inválido'}), 400

    data = request.get_json()
    nombre = data.get('nombre')
    descripcion = data.get('descripcion')
    imagen = data.get('imagen')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if imagen:
        cursor.execute(f"UPDATE {tabla} SET nombre=%s, descripcion=%s, imagen_url=%s WHERE id=%s",
                       (nombre, descripcion, imagen, serv_id))
    else:
        cursor.execute(f"UPDATE {tabla} SET nombre=%s, descripcion=%s WHERE id=%s",
                       (nombre, descripcion, serv_id))
    mysql.connection.commit()
    cursor.close()
    return jsonify({'status': 'ok', 'message': 'Servicio actualizado.'})

# -------------------- API: ELIMINAR SERVICIO --------------------
@app.route('/api/servicios/<tipo>/<int:serv_id>', methods=['DELETE'])
def eliminar_servicio_api(tipo, serv_id):
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': 'No autorizado'}), 403

    tablas = {
        'comida': 'comidas',
        'salones': 'salones',
        'djs': 'djs',
        'entretenimiento': 'entretenimientos'
    }
    tabla = tablas.get(tipo)
    if not tabla:
        return jsonify({'status': 'error', 'message': 'Tipo inválido'}), 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # intentar eliminar archivo si es de uploads local
    cursor.execute(f"SELECT imagen_url FROM {tabla} WHERE id=%s", (serv_id,))
    r = cursor.fetchone()
    if r and r.get('imagen_url'):
        img = r['imagen_url']
        if img.startswith('/static/uploads/servicios/'):
            try:
                filepath = img.lstrip('/')
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                print("No se pudo eliminar archivo:", e)

    cursor.execute(f"DELETE FROM {tabla} WHERE id=%s", (serv_id,))
    mysql.connection.commit()
    cursor.close()
    return jsonify({'status': 'ok', 'message': 'Servicio eliminado.'})
# -------------------- NUEVO SERVICIO DESDE FORMULARIO --------------------
@app.route('/api/servicios/nuevo', methods=['POST'])
def nuevo_servicio():
    if 'loggedin' not in session:
        return jsonify({'status': 'error', 'message': '⚠️ Debes iniciar sesión'}), 403

    data = request.get_json()
    tipo = data.get('tipo')
    nombre = data.get('nombre')
    descripcion = data.get('descripcion')
    imagen_url = data.get('imagen_url')

    tablas = {
        'comida': 'comidas',
        'salones': 'salones',
        'djs': 'djs',
        'entretenimiento': 'entretenimientos',
        'decoracion': 'decoraciones',
        'bebidas': 'bebidas'
    }

    tabla = tablas.get(tipo)
    if not tabla:
        return jsonify({'status': 'error', 'message': 'Tipo de servicio no válido'}), 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Crear tabla si no existe
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {tabla} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            imagen_url TEXT
        )
    """)

    cursor.execute(
        f"INSERT INTO {tabla} (nombre, descripcion, imagen_url) VALUES (%s, %s, %s)",
        (nombre, descripcion, imagen_url)
    )
    mysql.connection.commit()
    cursor.close()

    return jsonify({'status': 'ok', 'message': f"✅ Servicio '{nombre}' agregado correctamente"})

# -------------------- CHAT / RED SOCIAL --------------------
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Si el usuario publica algo nuevo
    if request.method == 'POST':
        contenido = request.form.get('contenido')
        file = request.files.get('imagen')
        imagen_url = save_uploaded_file(file) if file and file.filename else None

        if contenido:
            cursor.execute('INSERT INTO publicaciones (usuario_id, contenido, imagen_url) VALUES (%s, %s, %s)',
                           (session['id'], contenido, imagen_url))
            mysql.connection.commit()
            flash('🪩 Publicación agregada con éxito', 'success')

    # Mostrar todas las publicaciones (más recientes primero)
    cursor.execute('''
        SELECT p.id, p.contenido, p.imagen_url, p.fecha_publicacion,
               u.usuario, u.foto
        FROM publicaciones p
        JOIN usuarios u ON p.usuario_id = u.id
        ORDER BY p.fecha_publicacion DESC
    ''')
    publicaciones = cursor.fetchall()

    # Para cada publicación, obtenemos los comentarios
    for pub in publicaciones:
        cursor.execute('''
            SELECT c.comentario, c.fecha_comentario, u.usuario, u.foto
            FROM comentarios c
            JOIN usuarios u ON c.usuario_id = u.id
            WHERE c.publicacion_id = %s
            ORDER BY c.fecha_comentario ASC
        ''', (pub['id'],))
        pub['comentarios'] = cursor.fetchall()

    cursor.close()
    return render_template('chat.html', publicaciones=publicaciones, usuario=session['usuario'])
@app.route('/comentar/<int:pub_id>', methods=['POST'])
def comentar(pub_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    comentario = request.form.get('comentario')
    if not comentario:
        flash('⚠️ El comentario no puede estar vacío', 'warning')
        return redirect(url_for('chat'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('INSERT INTO comentarios (publicacion_id, usuario_id, comentario) VALUES (%s, %s, %s)',
                   (pub_id, session['id'], comentario))
    mysql.connection.commit()
    cursor.close()

    flash('💬 Comentario agregado', 'info')
    return redirect(url_for('chat'))
# -------------------- ACTUALIZAR PUBLICACIÓN --------------------
@app.route('/actualizar_publicacion/<int:id>', methods=['POST'])
def actualizar_publicacion(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM publicaciones WHERE id = %s AND usuario_id = %s', (id, session['id']))
    pub = cursor.fetchone()

    if not pub:
        flash('⚠️ No puedes editar esta publicación.', 'danger')
        return redirect(url_for('chat'))

    contenido = request.form.get('contenido')
    file = request.files.get('imagen')
    imagen_url = pub['imagen_url']

    if file and file.filename:
        imagen_url = save_uploaded_file(file)

    cursor.execute('UPDATE publicaciones SET contenido = %s, imagen_url = %s WHERE id = %s',
                   (contenido, imagen_url, id))
    mysql.connection.commit()
    cursor.close()
    flash('✅ Publicación actualizada correctamente', 'success')
    return redirect(url_for('chat'))


# -------------------- ELIMINAR PUBLICACIÓN --------------------
@app.route('/eliminar_publicacion/<int:id>', methods=['POST'])
def eliminar_publicacion(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM publicaciones WHERE id = %s AND usuario_id = %s', (id, session['id']))
    pub = cursor.fetchone()

    if not pub:
        flash('⚠️ No puedes eliminar esta publicación.', 'danger')
        return redirect(url_for('chat'))

    cursor.execute('DELETE FROM publicaciones WHERE id = %s', (id,))
    mysql.connection.commit()
    cursor.close()
    flash('🗑️ Publicación eliminada correctamente', 'info')
    return redirect(url_for('chat'))

# -------------------- NUEVA RUTA: GENERAR PDF DE UNA FIESTA --------------------
@app.route('/fiesta_pdf/<int:id>')
def fiesta_pdf(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT f.*, 
               c.nombre AS comida_nombre,
               s.nombre AS salon_nombre,
               d.nombre AS dj_nombre,
               e.nombre AS entretenimiento_nombre,
               u.usuario AS creador, u.foto AS creador_foto
        FROM fiestas f
        LEFT JOIN comidas c ON f.comida_id = c.id
        LEFT JOIN salones s ON f.salon_id = s.id
        LEFT JOIN djs d ON f.dj_id = d.id
        LEFT JOIN entretenimientos e ON f.entretenimiento_id = e.id
        LEFT JOIN usuarios u ON f.usuario_id = u.id
        WHERE f.id = %s AND f.usuario_id = %s
    ''', (id, session['id']))
    fiesta = cursor.fetchone()
    cursor.close()

    if not fiesta:
        flash('Fiesta no encontrada o no tienes permiso', 'danger')
        return redirect(url_for('perfil'))

    # Generar PDF en memoria
    buffer = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"Reporte: {fiesta.get('nombre','')}")
    y -= 30

    c.setFont("Helvetica", 12)
    campos = [
        ("Tipo", fiesta.get('tipo')),
        ("Ubicación", fiesta.get('ubicacion')),
        ("Fecha", str(fiesta.get('fecha')) if fiesta.get('fecha') else ''),
        ("Hora", str(fiesta.get('hora')) if fiesta.get('hora') else ''),
        ("Invitados", str(fiesta.get('invitados')) if fiesta.get('invitados') else ''),
        ("Salón", fiesta.get('salon_nombre')),
        ("Comida", fiesta.get('comida_nombre')),
        ("DJ", fiesta.get('dj_nombre')),
        ("Entretenimiento", fiesta.get('entretenimiento_nombre')),
        ("Creador", fiesta.get('creador'))
    ]

    for etiqueta, valor in campos:
        c.drawString(50, y, f"{etiqueta}: {valor or ''}")
        y -= 18
        if y < 60:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 12)

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"fiesta_{fiesta.get('id')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')
@app.route('/fiestas_pdf')
def fiestas_pdf():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT f.id, f.nombre, f.tipo, f.ubicacion, f.fecha, f.hora, f.invitados,
               c.nombre AS comida_nombre, s.nombre AS salon_nombre,
               d.nombre AS dj_nombre, e.nombre AS entretenimiento_nombre
        FROM fiestas f
        LEFT JOIN comidas c ON f.comida_id = c.id
        LEFT JOIN salones s ON f.salon_id = s.id
        LEFT JOIN djs d ON f.dj_id = d.id
        LEFT JOIN entretenimientos e ON f.entretenimiento_id = e.id
        WHERE f.usuario_id = %s
        ORDER BY f.fecha, f.hora
    ''', (session['id'],))
    fiestas = cursor.fetchall()
    cursor.close()

    buffer = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Reporte general de fiestas")
    y -= 30
    c.setFont("Helvetica", 11)

    if not fiestas:
        c.drawString(50, y, "No hay fiestas para mostrar.")
        y -= 20

    for f in fiestas:
        c.drawString(50, y, f"Nombre: {f.get('nombre') or ''}")
        y -= 14
        c.drawString(50, y, f"Tipo: {f.get('tipo') or ''}  |  Fecha: {f.get('fecha') or ''}  Hora: {f.get('hora') or ''}")
        y -= 14
        c.drawString(50, y, f"Ubicación: {f.get('ubicacion') or ''}  |  Invitados: {f.get('invitados') or ''}")
        y -= 14
        c.drawString(50, y, f"Salón: {f.get('salon_nombre') or ''}  |  Comida: {f.get('comida_nombre') or ''}")
        y -= 14
        c.drawString(50, y, f"DJ: {f.get('dj_nombre') or ''}  |  Entretenimiento: {f.get('entretenimiento_nombre') or ''}")
        y -= 22

        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 11)

    c.showPage()
    c.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name='fiestas_report.pdf', mimetype='application/pdf')
# -------------------- MAIN --------------------
if __name__ == '__main__':
    app.run(debug=True)
