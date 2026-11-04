import os

# Precisa valer antes de o Qt iniciar: os testes de interface não abrem janelas na tela.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
