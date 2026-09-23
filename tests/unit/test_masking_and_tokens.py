from mcphawk.protocol import masking, tokens
from mcphawk.protocol.masking import MASK


def test_mask_value_masks_secret_keys_but_not_lookalikes():
    data = {
        "api_key": "abc", "token": "t", "clientSecret": "s", "password": "p",
        "max_tokens": 100, "tokens_used": "12", "nested": [{"Authorization": "x"}],
        "empty_token": "",
    }
    masked = masking.mask_value(data)
    assert masked["api_key"] == masked["token"] == masked["password"] == MASK
    assert masked["nested"][0]["Authorization"] == MASK
    assert masked["max_tokens"] == 100
    assert masked["tokens_used"] == "12"
    assert masked["empty_token"] == ""


def test_mask_text_patterns():
    text = ("key sk-ant-abcdefghijklmnopqrstuv and ghp_" + "a" * 36 +
            " AKIAABCDEFGHIJKLMNOP Bearer abc.def.ghijklmnop")
    masked = masking.mask_text(text)
    assert "sk-ant" not in masked
    assert "ghp_" not in masked
    assert "AKIA" not in masked
    assert "abc.def" not in masked
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"
    assert masking.mask_text(jwt) == MASK
    assert masking.mask_text("plain text") == "plain text"


def test_mask_headers():
    masked = masking.mask_headers({"Authorization": "Bearer x", "Mcp-Method": "tools/call"})
    assert masked == {"Authorization": MASK, "Mcp-Method": "tools/call"}


def test_mask_argv():
    argv = ["server", "--api-key", "secret", "--token=abc", "--port", "80",
            "sk-abcdefghijklmnopqrstu"]
    assert masking.mask_argv(argv) == [
        "server", "--api-key", MASK, "--token=" + MASK, "--port", "80", MASK]


def test_token_estimates():
    assert tokens.estimate_text("") == 0
    assert tokens.estimate_text("abc") == 1
    assert tokens.estimate_text("a" * 400) == 100
    assert tokens.estimate_json(None) == 0
    assert tokens.estimate_json({"a": 1}) > 0
    blocks = [
        {"type": "text", "text": "a" * 40},
        {"type": "image", "data": "x" * 100000},
        {"type": "resource", "resource": {"text": "b" * 8}},
        {"type": "resource", "resource": {"blob": "zz"}},
        {"type": "resource_link", "uri": "file:///x"},
        "odd",
    ]
    total = tokens.estimate_content(blocks)
    assert total == 10 + tokens.IMAGE_TOKENS + 2 + tokens.IMAGE_TOKENS + \
        tokens.estimate_json(blocks[4]) + tokens.estimate_json("odd")
    assert tokens.estimate_content({"x": 1}) == tokens.estimate_json({"x": 1})
