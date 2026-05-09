import threading
import webbrowser
import time

from app import app


def abrir_navegador():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    threading.Thread(target=abrir_navegador).start()
    app.run(host="127.0.0.1", port=5000, debug=False)