
import os
import subprocess
import shutil
import stat
from pathlib import Path
from dotenv import load_dotenv

def on_error(func, path, exc_info):
    """Error handler for shutil.rmtree to handle read-only files on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def test_push():
    load_dotenv()
    repo_url = os.getenv("GITHUB_REPO_URL")
    token = os.getenv("GITHUB_TOKEN")
    
    if not repo_url or not token:
        print("❌ GITHUB_REPO_URL ou GITHUB_TOKEN manquant dans le .env")
        return

    # Nettoyage robuste
    test_dir = Path("test_git_write").absolute()
    if test_dir.exists():
        shutil.rmtree(test_dir, onerror=on_error)
    
    # URL avec Token
    auth_url = repo_url.replace("https://", f"https://{token}@")
    
    try:
        print(f"🔄 Test de clone depuis {repo_url}...")
        result_clone = subprocess.run(["git", "clone", "--depth", "1", auth_url, str(test_dir)], capture_output=True, text=True)
        
        if result_clone.returncode != 0:
            print(f"❌ Échec du clone : {result_clone.stderr}")
            return
            
        print("✅ Clone réussi (Lecture OK)")
        
        # Test d'écriture : créer un fichier et tenter un push
        (test_dir / "test_write.txt").write_text("Test write access")
        
        subprocess.run(["git", "config", "user.name", "Test Agent"], cwd=test_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@agent.com"], cwd=test_dir, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=test_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Test write access"], cwd=test_dir, capture_output=True)
        
        print("📤 Tentative de push...")
        # On tente de pusher sur une branche de test pour ne pas polluer le main
        result = subprocess.run(["git", "push", "origin", "main:test-write-permission"], cwd=test_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("🚀 SUCCÈS ! Le token a les droits d'écriture.")
        else:
            print(f"❌ ÉCHEC DU PUSH (Droit d'écriture manquant) :\n{result.stderr}")
            
    except Exception as e:
        print(f"💥 Erreur lors du test : {e}")
    finally:
        # Nettoyage final
        if test_dir.exists():
            shutil.rmtree(test_dir, onerror=on_error)

if __name__ == "__main__":
    test_push()
