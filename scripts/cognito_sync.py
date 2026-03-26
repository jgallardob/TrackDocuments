import json
import boto3
import argparse
import sys

def sync_users_to_cognito(user_pool_id: str, db_path: str = '../users_db.json'):
    """
    Sincroniza un listado JSON local pre-existente con un servidor de AWS Cognito User Pools.
    Asume que el user_pool ya existe dentro de la cuenta AWS.
    """
    client = boto3.client('cognito-idp')
    
    try:
        with open(db_path, 'r') as file:
            users_list = json.load(file)
            
        for user in users_list:
            
            # Formateo de las variables maestras de migración
            username = user.get("username")
            user_id = user.get("user_id")
            temp_password = "Password123!" # Cognito forzara cambio pero requiere estricto
            status = user.get("status")

            if not username:
                continue
                
            print(f"Sincronizando usuario AWS: {username} (ID: {user_id})...")
            
            try:
                # Cognito: Creacion Forzada
                response = client.admin_create_user(
                    UserPoolId=user_pool_id,
                    Username=username,
                    UserAttributes=[
                        {'Name': 'custom:internal_id', 'Value': user_id},
                    ],
                    TemporaryPassword=temp_password,
                    MessageAction='SUPPRESS' # Deshabilita correos de invitacion
                )
                
                # Seta password directa real si se pudiese de forma deterministica (a fines de demo)
                client.admin_set_user_password(
                    UserPoolId=user_pool_id,
                    Username=username,
                    Password="AdminPass123_aws!",
                    Permanent=True
                )
                
                # Deshabilita el usuario si en local esta marcado asi
                if status == "disabled":
                     client.admin_disable_user(
                        UserPoolId=user_pool_id,
                        Username=username
                     )
                     print(f"    --> {username} migrado inactivo.")
                else:
                    print(f"    --> {username} sincronizado correctamente de forma activa.")

            except client.exceptions.UsernameExistsException:
                print(f"    --> Usuario {username} ya es existente. Omitiendo.")
                
            except Exception as creation_error:
                print(f"    --> ERROR con {username}: {str(creation_error)}")
                
    except FileNotFoundError:
        print(f"No se detecta el archivo local de usuarios {db_path}.")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script Mapeo JSON -> AWS Cognito")
    parser.add_argument("--pool-id", required=True, help="El ID del User Pool de destino")
    parser.add_argument("--json", default='../users_db.json', help="Ruta al DB JSON local")
    
    args = parser.parse_args()
    sync_users_to_cognito(args.pool_id, args.json)
