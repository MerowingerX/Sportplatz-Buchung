def toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'
