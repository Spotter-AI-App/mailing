import smtplib
import csv
import os
import socket
import json
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from dotenv import load_dotenv

load_dotenv()

# SMTP configuration (information relative to server name and port found in arsys/correo/configuración)
SMTP_SERVER = "smtp.serviciodecorreo.es"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = SMTP_USER

# Paths configuration
SCRIPT_DIR = os.path.dirname(__file__)
CAMPAIGNS_DIR = os.path.join(SCRIPT_DIR, "campaigns")

# Default campaign (for backwards compatibility)
DEFAULT_CAMPAIGN = "beta_invitation"


def list_campaigns():
    """List all available campaigns."""
    campaigns = []
    if os.path.exists(CAMPAIGNS_DIR):
        for folder in os.listdir(CAMPAIGNS_DIR):
            campaign_path = os.path.join(CAMPAIGNS_DIR, folder)
            config_file = os.path.join(campaign_path, "config.json")
            if os.path.isdir(campaign_path) and os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                campaigns.append({
                    'id': folder,
                    'name': config.get('name', folder),
                    'path': campaign_path
                })
    return campaigns


def load_campaign_config(campaign_id):
    """Load campaign configuration from config.json.
    
    Args:
        campaign_id: Folder name of the campaign
    
    Returns:
        Dict with campaign configuration or None if not found
    """
    campaign_path = os.path.join(CAMPAIGNS_DIR, campaign_id)
    config_file = os.path.join(campaign_path, "config.json")
    
    if not os.path.exists(config_file):
        print(f"Error: No se encontró la campaña '{campaign_id}'")
        print(f"Campañas disponibles:")
        for c in list_campaigns():
            print(f"   - {c['id']}: {c['name']}")
        return None
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    config['path'] = campaign_path
    config['images_dir'] = os.path.join(campaign_path, "images")
    
    # Find any .csv file inside the campaign folder
    csv_files = [f for f in os.listdir(campaign_path) if f.lower().endswith('.csv')]
    if csv_files:
        config['csv_file'] = os.path.join(campaign_path, csv_files[0])
    else:
        config['csv_file'] = None
    
    return config


def load_html_template(campaign_config, language='es'):
    """Load the HTML template file based on language.
    
    Args:
        campaign_config: Campaign configuration dict
        language: 'es' for Spanish, 'en' for English (default: 'es')
    
    Returns:
        HTML template string or None if file not found
    """
    template_name = campaign_config.get('templates', {}).get(language, 'template_es.html')
    template_file = os.path.join(campaign_config['path'], template_name)
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo HTML {template_file}")
        return None


def load_all_templates(campaign_config):
    """Load both Spanish and English templates.
    
    Args:
        campaign_config: Campaign configuration dict
    
    Returns:
        Dict with 'es' and 'en' keys containing respective templates
    """
    return {
        'es': load_html_template(campaign_config, 'es'),
        'en': load_html_template(campaign_config, 'en')
    }


def get_images_to_embed(campaign_config):
    """Get list of images to embed in the email.
    
    Args:
        campaign_config: Campaign configuration dict
    """
    images = {}
    images_dir = campaign_config.get('images_dir')
    if images_dir and os.path.exists(images_dir):
        for filename in os.listdir(images_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                filepath = os.path.join(images_dir, filename)
                images[filename] = filepath
    return images


def create_html_email(nombre, html_template, images, subject):
    """
    Create email with embedded images.
    
    Args:
        nombre: Recipient name for personalization
        html_template: HTML template string
        images: Dict of {filename: filepath} for images to embed
        subject: Email subject line
    
    Returns:
        MIMEMultipart message ready to send
    """
    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    
    # Create alternative part for HTML
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)
    
    # Personalize HTML with recipient name (use only first name)
    first_name = nombre.split()[0]
    personalized_html = html_template.replace('$name', first_name)
    
    # Replace image paths with CID references for embedded images
    for filename in images.keys():
        # Create a unique Content-ID for each image
        cid = filename.replace('.', '_')
        personalized_html = personalized_html.replace(
            f'src="images/{filename}"',
            f'src="cid:{cid}"'
        )
    
    # Attach HTML part
    html_part = MIMEText(personalized_html, 'html', 'utf-8')
    msg_alternative.attach(html_part)
    
    # Attach images
    for filename, filepath in images.items():
        try:
            with open(filepath, 'rb') as img_file:
                img_data = img_file.read()
                img = MIMEImage(img_data)
                cid = filename.replace('.', '_')
                img.add_header('Content-ID', f'<{cid}>')
                msg.attach(img)
        except FileNotFoundError:
            print(f"  ⚠️ Imagen no encontrada: {filepath}")
    
    return msg


def enviar_correos(campaign_id=None):
    """Main function to send emails.
    
    Args:
        campaign_id: ID of the campaign to send (folder name)
    """
    
    # Use default campaign if none specified
    if not campaign_id:
        campaign_id = DEFAULT_CAMPAIGN
    
    # 0. Load campaign configuration
    campaign_config = load_campaign_config(campaign_id)
    if not campaign_config:
        return
    
    print(f"\n📧 Campaña: {campaign_config.get('name', campaign_id)}")
    print(f"📁 Ruta: {campaign_config['path']}")
    
    # Check if CSV file exists
    if not campaign_config['csv_file']:
        print(f"❌ Error: No se encontró ningún archivo .csv en la carpeta de la campaña")
        return
    
    print(f"📄 CSV: {campaign_config['csv_file']}")
    
    # 1. Load HTML templates (Spanish and English)
    templates = load_all_templates(campaign_config)
    if not templates['es'] and not templates['en']:
        print("Error: No se pudieron cargar las plantillas HTML")
        return
    
    print(f"\n📝 Plantillas cargadas:")
    print(f"   - Español (ES): {'✅' if templates['es'] else '❌'}")
    print(f"   - English (EN): {'✅' if templates['en'] else '❌'}")
    
    # 2. Get images to embed
    images = get_images_to_embed(campaign_config)
    print(f"\n📷 Imágenes encontradas: {len(images)}")
    for img in images.keys():
        print(f"   - {img}")
    
    # Get email subjects from campaign config
    subjects = campaign_config.get('subjects', {
        'es': "Spotter AI",
        'en': "Spotter AI"
    })
    
    # 3. Read CSV file from campaign folder
    csv_file = campaign_config['csv_file']
    contactos = []
    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            contactos = list(reader)
            if not contactos:
                print("El archivo CSV está vacío.")
                return
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {csv_file}")
        return
    
    # Count pending emails
    pendientes = sum(1 for c in contactos if c.get('enviado', 'no').lower().strip() != 'si')
    print(f"\n📧 Emails pendientes: {pendientes}")
    
    if pendientes == 0:
        print("✅ Todos los emails ya han sido enviados.")
        return
    
    # 4. Connect to SMTP server
    try:
        print(f"\n🔌 Conectando a {SMTP_SERVER}:{SMTP_PORT}...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.set_debuglevel(0)  # Set to 1 for debug output
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        print("✅ Conexión establecida")
        
        # 5. Send emails
        enviados = 0
        for contacto in contactos:
            nombre = contacto.get('nombre', '').split()[0].strip()
            email = contacto.get('email', '').lower().strip()
            enviado = contacto.get('enviado', 'no').lower().strip()
            device = contacto.get('device', 'no').lower().strip()
            language = contacto.get('language', 'es').lower().strip()
            
            # Validate language, default to 'es' if invalid
            if language not in ['es', 'en']:
                language = 'es'
            
            if not nombre or not email or device == 'android':
                print(f"⚠️ Saltando fila: nombre='{nombre}', email='{email}', device='{device}'")
                continue
            
            if enviado == 'si':
                continue
            
            # Get the appropriate template for the language
            html_template = templates.get(language)
            if not html_template:
                print(f"⚠️ No hay plantilla para idioma '{language}', usando español")
                html_template = templates['es']
                language = 'es'
            
            # Get subject for the language
            subject = subjects.get(language, subjects.get('es', 'Spotter AI'))
            
            lang_label = '🇪🇸' if language == 'es' else '🇬🇧'
            print(f"\n📤 Enviando a {nombre} ({email}) {lang_label}...")
            
            try:
                # Create personalized email with correct language template and subject
                msg = create_html_email(nombre, html_template, images, subject)
                msg['From'] = "Spotter AI <info@spotter-ai.app>"
                msg['To'] = email
                
                # Send email
                server.sendmail(SENDER_EMAIL, email, msg.as_string())
                contacto['enviado'] = 'si'
                enviados += 1
                print(f"   ✅ Enviado correctamente")
                
            except Exception as e:
                print(f"   ❌ Error al enviar: {e}")
        
        server.quit()
        print(f"\n🎉 Total enviados: {enviados}/{pendientes}")
        
        # 6. Update CSV file
        with open(csv_file, mode='w', encoding='utf-8', newline='') as f:
            fieldnames = ['nombre', 'email', 'device', 'enviado', 'language']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(contactos)
        print("📝 CSV actualizado")
        
    except smtplib.SMTPAuthenticationError:
        print("\n❌ ERROR DE AUTENTICACIÓN: Usuario o contraseña incorrectos.")
    except socket.gaierror:
        print("\n❌ ERROR DE DNS: No se encuentra el servidor.")
    except ConnectionRefusedError:
        print("\n❌ CONEXIÓN RECHAZADA: El servidor o el puerto están bloqueados.")
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Spotter AI - Email Campaign Sender')
    parser.add_argument('--campaign', '-c', type=str, default=None,
                        help='Campaign folder name to send (e.g., beta_invitation, build7_update)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List available campaigns')
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("📨 SPOTTER AI - ENVÍO DE EMAILS")
    print("=" * 50)
    
    if args.list:
        print("\n📋 Campañas disponibles:")
        for campaign in list_campaigns():
            print(f"   - {campaign['id']}: {campaign['name']}")
    else:
        enviar_correos(args.campaign)
