"""
Blueprint per la gestione delle categorie
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.categorie_service import CategorieService

categorie_bp = Blueprint('categorie', __name__)

@categorie_bp.route('/')
def lista():
    """Lista delle categorie"""
    try:
        service = CategorieService()
        
        # Recupera tutte le categorie
        categorie = service.get_all_categories()
        
        return render_template('categorie.html', categorie=categorie)
        
    except Exception as e:
        flash(f'Errore nel caricamento delle categorie: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@categorie_bp.route('/nuova', methods=['GET', 'POST'])
def nuova():
    """Crea una nuova categoria"""
    if request.method == 'GET':
        return render_template('categorie/nuova.html')
    
    try:
        service = CategorieService()
        
        nome = request.form['nome'].strip()
        tipo = request.form['tipo']
        
        if not nome:
            flash('Il nome della categoria è obbligatorio', 'error')
            return render_template('categorie/nuova.html')
        
        success, message = service.create_categoria(nome, tipo)
        
        if success:
            flash(message, 'success')
            return redirect(url_for('categorie.lista'))
        else:
            flash(message, 'error')
            return render_template('categorie/nuova.html')
            
    except Exception as e:
        flash(f'Errore nella creazione: {str(e)}', 'error')
        return render_template('categorie/nuova.html')

@categorie_bp.route('/aggiungi', methods=['POST'])
def aggiungi():
    """Aggiungi categoria via form rapido"""
    try:
        service = CategorieService()
        
        nome = request.form['nome'].strip()
        tipo = request.form['tipo']
        
        if not nome:
            flash('Il nome della categoria è obbligatorio', 'error')
            return redirect(url_for('categorie.lista'))
        
        success, message = service.create_categoria(nome, tipo)
        flash(message, 'success' if success else 'error')
        
    except Exception as e:
        flash(f'Errore: {str(e)}', 'error')
    
    return redirect(url_for('categorie.lista'))

@categorie_bp.route('/<int:categoria_id>/modifica', methods=['GET', 'POST'])
def modifica(categoria_id):
    """Modifica una categoria esistente"""
    service = CategorieService()
    
    if request.method == 'GET':
        from app.models.base import Categoria
        categoria = Categoria.query.get_or_404(categoria_id)
        return render_template('categorie/modifica.html', categoria=categoria)
    
    try:
        nome = request.form.get('nome', '').strip()
        tipo = request.form.get('tipo')
        
        success, message = service.update_categoria(categoria_id, nome=nome, tipo=tipo)
        
        if success:
            flash(message, 'success')
            return redirect(url_for('categorie.lista'))
        else:
            flash(message, 'error')
            
    except Exception as e:
        flash(f'Errore: {str(e)}', 'error')
    
    # Ricarica il form in caso di errore
    from app.models.base import Categoria
    categoria = Categoria.query.get_or_404(categoria_id)
    return render_template('categorie/modifica.html', categoria=categoria)

@categorie_bp.route('/<int:categoria_id>/elimina', methods=['POST'])
def elimina(categoria_id):
    """Elimina una categoria"""
    try:
        service = CategorieService()
        success, message = service.delete_categoria(categoria_id)
        flash(message, 'success' if success else 'error')
        
    except Exception as e:
        flash(f'Errore: {str(e)}', 'error')
    
    return redirect(url_for('categorie.lista'))
