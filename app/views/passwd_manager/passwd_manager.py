from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app, session, redirect, url_for
from app.services.passwd_manager.passwd_manager_service import (
    initialize_encryption, is_initialized, has_security_config,
    get_all_credentials, search_credentials, get_categories, add_credential,
    update_credential, delete_credential, get_credential_by_id_decrypted,
    export_to_xlsx
)
from werkzeug.utils import secure_filename
import os
import hashlib

bp = Blueprint('passwd', __name__, template_folder='templates')


def hash_password(password):
    """Genera un hash SHA256 della password"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


@bp.route('/')
def index():
    # If the passwd manager hasn't been configured, inform the operator.
    # The previous automatic reconfiguration/setup flow has been removed.
    if not has_security_config():
        return ("Password Manager non configurato. Contatta l'amministratore per la configurazione.", 503)
    
    # Verifica che la sessione sia autenticata
    if not session.get('authenticated') or not session.get('password_hash'):
        return redirect(url_for('passwd.login'))
    
    # If the encryption system is not yet initialized, redirect to the login page
    if not is_initialized():
        return redirect(url_for('passwd.login'))

    # Build categories mapping expected by the template
    data = get_all_credentials()
    categories = {}
    for item in data:
        cat = item.get('CATEGORIA') or 'SENZA_CATEGORIA'
        categories.setdefault(cat, []).append(item)

    return render_template('passwd_manager/index.html', categories=categories)


# NOTE: setup route and reconfiguration UI were removed intentionally.
# If you need to re-enable interactive setup, restore a safe setup flow
# that requires authenticated administrative access outside of the public UI.


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if initialize_encryption(password):
            session.permanent = True  # Attiva la durata configurata (3 minuti)
            session['authenticated'] = True
            session['password_hash'] = hash_password(password)  # Memorizza solo l'hash
            return redirect(url_for('main.index'))
        return render_template('login.html', error='Invalid password')
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.pop('authenticated', None)
    session.pop('password_hash', None)
    return redirect(url_for('passwd.login'))


@bp.route('/api/search')
def api_search():
    q = request.args.get('q')
    cat = request.args.get('categoria')
    results = search_credentials(q, cat)
    return jsonify(results)


@bp.route('/api/credentials', methods=['GET', 'POST'])
def api_credentials():
    if request.method == 'GET':
        return jsonify(get_all_credentials())
    data = request.get_json() or {}
    cid = add_credential(data.get('CATEGORIA'), data.get('SERVIZIO'), data.get('UTENZA'), data.get('PASSWORD'), data.get('ALTRO'))
    return jsonify({'id': cid})


@bp.route('/api/credentials/<int:cid>', methods=['PUT', 'DELETE'])
def api_credential_item(cid):
    if request.method == 'DELETE':
        ok = delete_credential(cid)
        return jsonify({'ok': ok})
    data = request.get_json() or {}
    ok = update_credential(cid, data.get('CATEGORIA'), data.get('SERVIZIO'), data.get('UTENZA'), data.get('PASSWORD'), data.get('ALTRO'))
    return jsonify({'ok': ok})


@bp.route('/api/categories')
def api_categories():
    return jsonify(get_categories())


@bp.route('/api/categories-with-counts')
def api_categories_with_counts():
    cats = get_categories()
    # build mapping
    mapping = {c: len(search_credentials(None, c)) for c in cats}
    return jsonify(mapping)


@bp.route('/api/credentials/<int:cid>/decrypted')
def api_credential_decrypted(cid):
    c = get_credential_by_id_decrypted(cid)
    return jsonify(c or {})


@bp.route('/api/export/xlsx')
def api_export_xlsx():
    path = export_to_xlsx()
    if not path:
        return jsonify({'ok': False}), 500
    directory, filename = os.path.split(path)
    return send_from_directory(directory, filename, as_attachment=True)


# Serve service worker file expected at /passwd/sw.js
@bp.route('/sw.js')
def service_worker():
    # The service worker file is placed under app/static/passwd/sw.js
    sw_dir = os.path.join(current_app.root_path, 'static', 'passwd')
    return send_from_directory(sw_dir, 'sw.js', mimetype='application/javascript')
