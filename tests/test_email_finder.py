from pipeline.contacts.email_finder import _extrair_emails_de_html


def test_extrai_email_em_texto_solto():
    html = "<html><body><p>Contacte-nos: geral@riamolde.com</p></body></html>"
    assert _extrair_emails_de_html(html) == {"geral@riamolde.com"}


def test_extrai_email_de_mailto():
    html = '<a href="mailto:comercial@riamolde.com?subject=Ola">Email</a>'
    assert _extrair_emails_de_html(html) == {"comercial@riamolde.com"}


def test_ignora_email_de_imagem_retina():
    html = "<p>logo@2x.png geral@riamolde.com</p>"
    assert _extrair_emails_de_html(html) == {"geral@riamolde.com"}


def test_ignora_dominios_excluidos():
    html = "<p>suporte@sentry.io geral@riamolde.com noreply@wixpress.com</p>"
    assert _extrair_emails_de_html(html) == {"geral@riamolde.com"}


def test_multiplos_emails_distintos():
    html = "<p>geral@riamolde.com</p><p>rh@riamolde.com</p>"
    resultado = _extrair_emails_de_html(html)
    assert resultado == {"geral@riamolde.com", "rh@riamolde.com"}


def test_sem_emails():
    html = "<html><body><h1>Bem-vindo</h1></body></html>"
    assert _extrair_emails_de_html(html) == set()
