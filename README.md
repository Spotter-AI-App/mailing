# Mailing

## Requisitos

Archivo .env con las variables de entorno:

- SMTP_USER
- SMTP_PASSWORD

## Uso

```bash
python mailing.py --list                  # Ver campañas disponibles
python mailing.py --campaign <nombre>     # Enviar campaña
```

## Nueva campaña

1. Duplica una carpeta existente en `campaigns/`
2. Renómbrala con el nombre de tu campaña
3. Edita `config.json` con el nombre y asuntos del email
4. Añade tus templates HTML (es y en)
5. Pon tu archivo `.csv` con los contactos
6. Añade las imágenes en `images/`

## Formato CSV

```csv
nombre,email,device,language,enviado
Juan García,juan@email.com,ios,es,no
```

| Campo    | Descripción                          |
| -------- | ------------------------------------ |
| nombre   | Nombre completo                      |
| email    | Email del destinatario               |
| device   | `ios` o `android` (android se salta) |
| language | `es` o `en`                          |
| enviado  | Se actualiza a `si` automáticamente  |

## Disclaimer

No es un buen approach. Usar .csv no es escalable y la lógica habría que darle una vuelta. De momento hace el apaño.
