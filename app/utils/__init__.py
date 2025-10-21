"""
Utilità comuni per l'applicazione
"""
from datetime import datetime, date
import calendar

class FormatterUtils:
    """Utilità per la formattazione"""
    
    @staticmethod
    def format_currency(amount, format_string="€ {:.2f}"):
        """Formatta un importo come valuta"""
        return format_string.format(amount)
    
    @staticmethod
    def format_date(date_obj, format_string="%d/%m/%Y"):
        """Formatta una data"""
        if isinstance(date_obj, str):
            return date_obj
        return date_obj.strftime(format_string)
    
    @staticmethod
    def format_datetime(datetime_obj, format_string="%d/%m/%Y %H:%M"):
        """Formatta una data con ora"""
        if isinstance(datetime_obj, str):
            return datetime_obj
        return datetime_obj.strftime(format_string)

class ValidationUtils:
    """Utilità per la validazione"""
    
    @staticmethod
    def validate_amount(amount_str):
        """Valida e converte un importo"""
        try:
            amount = float(amount_str.replace(',', '.'))
            if amount < 0:
                raise ValueError("L'importo non può essere negativo")
            return amount
        except (ValueError, AttributeError):
            raise ValueError("Importo non valido")
    
    @staticmethod
    def validate_date(date_str):
        """Valida e converte una data"""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError("Formato data non valido (YYYY-MM-DD)")
    
    @staticmethod
    def validate_required_field(value, field_name):
        """Valida che un campo obbligatorio non sia vuoto"""
        if not value or not value.strip():
            raise ValueError(f"Il campo {field_name} è obbligatorio")
        return value.strip()

class SecurityUtils:
    """Utilità per la sicurezza"""
    
    @staticmethod
    def sanitize_string(input_str, max_length=None):
        """Sanitizza una stringa di input"""
        if not input_str:
            return ""
        
        # Rimuove caratteri potenzialmente pericolosi
        sanitized = input_str.strip()
        
        # Tronca se necessario
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    @staticmethod
    def validate_file_extension(filename, allowed_extensions):
        """Valida l'estensione di un file"""
        if '.' not in filename:
            return False
        
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in allowed_extensions

class BusinessLogicUtils:
    """Utilità per la logica di business"""
    
    @staticmethod
    def calculate_monthly_boundaries(reference_date, start_day=27):
        """Calcola i confini del mese finanziario personalizzato"""
        if reference_date.day >= start_day:
            # Il mese inizia da questo giorno
            month_start = reference_date.replace(day=start_day)
            if reference_date.month == 12:
                month_end = date(reference_date.year + 1, 1, start_day - 1)
            else:
                try:
                    month_end = date(reference_date.year, reference_date.month + 1, start_day - 1)
                except ValueError:
                    # Il giorno non esiste nel mese successivo
                    days_in_next_month = calendar.monthrange(reference_date.year, reference_date.month + 1)[1]
                    month_end = date(reference_date.year, reference_date.month + 1, min(start_day - 1, days_in_next_month))
        else:
            # Il mese è iniziato il mese scorso
            if reference_date.month == 1:
                month_start = date(reference_date.year - 1, 12, start_day)
            else:
                month_start = date(reference_date.year, reference_date.month - 1, start_day)
            month_end = reference_date.replace(day=start_day - 1)
        
        return month_start, month_end
    
    @staticmethod
    def is_recurring_due(last_date, frequency_days, today=None):
        """Determina se una transazione ricorrente è dovuta"""
        if today is None:
            today = date.today()
        
        days_passed = (today - last_date).days
        return days_passed >= frequency_days
