from pipeline.analysis.chatbot_detection import detect_widget


def test_deteta_intercom():
    html = '<script src="https://widget.intercom.io/widget/abc123"></script>'
    assert detect_widget(html) == "intercom"


def test_deteta_drift():
    html = '<script src="https://js.driftt.com/include/123/abc.js"></script>'
    assert detect_widget(html) == "drift"


def test_deteta_tawkto():
    html = '<script src="https://embed.tawk.to/abc/default"></script>'
    assert detect_widget(html) == "tawk.to"


def test_deteta_generico_por_id():
    html = '<div id="my-chat-widget" class="foo"></div>'
    assert detect_widget(html) == "generico"


def test_sem_widget():
    html = "<html><body><h1>Bem-vindo</h1></body></html>"
    assert detect_widget(html) is None


def test_html_vazio():
    assert detect_widget("") is None
