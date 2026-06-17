"""Tests del helper de imágenes inline del worker (cid: → data:base64).

Unitarios sobre función pura. Corre dentro del contenedor (sys.path /app).
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/app")
from master_worker_outlook import _inline_images_a_base64

# contentBytes "QUJD" == base64 de "ABC"


def test_reemplaza_cid_por_base64():
    em = {
        "body": '<p>Hola</p><img src="cid:logo001"> fin',
        "attachments": [
            {"name": "logo.png", "contentId": "logo001", "isInline": True,
             "contentType": "image/png", "contentBytes": "QUJD"},
        ],
    }
    out = _inline_images_a_base64(em, "OUTLOOK")
    assert "data:image/png;base64,QUJD" in out
    assert "cid:logo001" not in out


def test_contentid_con_angle_brackets():
    em = {
        "body": '<img src="cid:img@x.com">',
        "attachments": [
            {"contentId": "<img@x.com>", "contentType": "image/jpeg",
             "contentBytes": "QUJD", "isInline": True},
        ],
    }
    out = _inline_images_a_base64(em, "OUTLOOK")
    assert "data:image/jpeg;base64,QUJD" in out


def test_cid_sin_match_queda_intacto():
    em = {"body": '<img src="cid:noexiste">', "attachments": []}
    assert "cid:noexiste" in _inline_images_a_base64(em, "OUTLOOK")


def test_zoho_no_se_toca():
    em = {"body": '<img src="cid:x">',
          "attachments": [{"contentId": "x", "contentBytes": "QQ==", "contentType": "image/png"}]}
    assert _inline_images_a_base64(em, "ZOHO") == '<img src="cid:x">'


def test_imagen_sobre_cap_se_saltea():
    big = "A" * 3_000_000
    em = {"body": '<img src="cid:big">',
          "attachments": [{"contentId": "big", "contentBytes": big,
                           "contentType": "image/png", "isInline": True}]}
    out = _inline_images_a_base64(em, "OUTLOOK")
    assert "cid:big" in out
    assert "data:image" not in out


def test_sin_cid_devuelve_igual():
    em = {"body": "<p>sin imagenes</p>", "attachments": []}
    assert _inline_images_a_base64(em, "OUTLOOK") == "<p>sin imagenes</p>"
