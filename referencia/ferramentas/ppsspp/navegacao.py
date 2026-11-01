"""Navegação rápida (sem verificação caixa a caixa)."""
import time

RAM0, RAMSZ = 0x08800000, 0x01800000


def avancar_ate_texto(p, texto, prazo=900, intervalo=1.2, checar_cada=8, log=None):
    """Aperta ○ repetidamente até `texto` (UTF-16) aparecer na RAM. -> True/False.
    Lembrete: o motor pré-carrega a próxima fala, então ao retornar o texto pode
    estar UMA caixa à frente da tela."""
    alvo = texto.encode("utf-16-le")
    t0, k = time.time(), 0
    while time.time() - t0 < prazo:
        if k % checar_cada == 0:
            p.pause()
            try:
                if alvo in p.dump_ram(RAM0, RAMSZ):
                    if log is not None:
                        log.append(("alvo_encontrado", round(time.time() - t0, 1), k))
                    return True
            finally:
                p.resume()
        p.press("circle", 3)
        time.sleep(intervalo)
        k += 1
    return False
