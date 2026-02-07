import asyncio
import asyncpg
from passlib.context import CryptContext
import uuid

# Configuration du hash de mot de passe (doit correspondre au backend)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_test_user():
    print("Tentative de création d'un utilisateur de test...")
    
    email = "admin@example.com"
    password = "admin1234"
    hashed_password = pwd_context.hash(password)
    name = "Directeur QA"
    role = "admin"
    
    try:
        # Connexion à la base de données
        conn = await asyncpg.connect(
            user='postgres', 
            password='1234', 
            database='ai_qa_saas', 
            host='127.0.0.1'
        )
        
        # Vérifier si l'utilisateur existe déjà
        user = await conn.fetchrow('SELECT id FROM users WHERE email = $1', email)
        
        if user:
            print(f"ℹ️ L'utilisateur {email} existe déjà.")
        else:
            # Insérer l'utilisateur
            # Note: id est généré par PostgreSQL via gen_random_uuid()
            # ou on peut le passer manuellement. On va laisser la DB le faire.
            await conn.execute('''
                INSERT INTO users (email, hashed_password, name, role, is_active)
                VALUES ($1, $2, $3, $4, $5)
            ''', email, hashed_password, name, role, True)
            
            print(f"✅ Utilisateur {email} créé avec succès !")
            print(f"📧 Email : {email}")
            print(f"🔑 Password : {password}")
            
        await conn.close()
        
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    asyncio.run(create_test_user())
