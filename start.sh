#!/bin/bash

# Script di avvio per la webapp di gestione bilancio familiare
# Aggiornato: 11 Settembre 2025 - Ottimizzazione porte e pulizia riferimenti

echo "==================================="
echo "Gestione Bilancio Familiare"
echo "==================================="
echo

# Controlla se Docker è installato
if ! command -v docker &> /dev/null; then
    echo "❌ Docker non è installato. Per installarlo:"
    echo "   Ubuntu/Debian: sudo apt update && sudo apt install docker.io docker-compose"
    echo "   CentOS/RHEL: sudo yum install docker docker-compose"
    exit 1
fi

# Controlla se Docker Compose è installato
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose non è installato. Per installarlo:"
    echo "   sudo apt update && sudo apt install docker-compose"
    exit 1
fi

# Crea la directory per i dati se non esiste
mkdir -p data

echo "🚀 Avvio dell'applicazione..."
echo

# Avvia i container
docker-compose up --build -d

# Attendi che l'applicazione sia pronta
echo "⏳ Attendo che l'applicazione sia pronta..."
sleep 5

# Controlla se l'applicazione è in esecuzione
if curl -s http://localhost:5001 > /dev/null; then
    echo "✅ Applicazione avviata con successo!"
    echo
    echo "🌐 Accedi all'applicazione su: http://localhost:5001"
    echo
    echo "📊 Funzionalità disponibili:"
    echo "   • Dashboard con panoramica 6 mesi"
    echo "   • Gestione entrate e uscite"
    echo "   • Categorie personalizzabili"
    echo "   • Transazioni ricorrenti"
    echo "   • Grafici e statistiche"
    echo
    echo "🛑 Per fermare l'applicazione: docker-compose down"
    echo "📋 Per vedere i log: docker-compose logs -f"
else
    echo "❌ Errore nell'avvio dell'applicazione"
    echo "📋 Controlla i log con: docker-compose logs"
    exit 1
fi
