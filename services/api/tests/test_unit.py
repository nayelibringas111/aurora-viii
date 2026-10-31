"""Pruebas unitarias: validación de arquitectura, transiciones de estado, permisos y datasets."""
import pytest

from app.core.permissions import ROLE_PERMS, Perm
from app.modules.architectures import ArchitectureError, Limits, compatibility, validate
from app.modules.catalog import FAMILIES
from app.modules.datasets import DatasetError, builtin_metadata, load_arrays, parse_csv, split_arrays
from app.modules.jobs import TERMINAL, can_transition

TPL = {f["id"]: f["template"] for f in FAMILIES}


@pytest.mark.parametrize("family", ["feedforward", "cnn", "rnn", "gan"])
def test_templates_are_valid(family):
    cfg, summary = validate(family, TPL[family])
    assert summary["total_params"] > 0


def test_dense_param_count():
    _, s = validate("feedforward", {"input_shape": [2], "layers": [{"type": "dense", "units": 4, "activation": "relu"}],
                                    "output": {"units": 3, "activation": "softmax"}})
    assert s["total_params"] == (2 * 4 + 4) + (4 * 3 + 3)


def test_keras_param_counts_match():
    """Los parámetros calculados sin TensorFlow coinciden con los de Keras."""
    from aurora_worker.builder import build_classifier
    for fam in ("feedforward", "cnn", "rnn"):
        cfg, s = validate(fam, TPL[fam])
        assert build_classifier(cfg).count_params() == s["total_params"], fam


def test_cnn_requires_flatten_before_dense():
    with pytest.raises(ArchitectureError) as e:
        validate("cnn", {"input_shape": [8, 8, 1], "layers": [{"type": "conv2d", "filters": 4, "kernel": 3, "activation": "relu"},
                                                             {"type": "dense", "units": 8, "activation": "relu"}],
                         "output": {"units": 4, "activation": "softmax"}})
    assert "Flatten" in str(e.value)


def test_stacked_rnn_needs_return_sequences():
    with pytest.raises(ArchitectureError):
        validate("rnn", {"input_shape": [24, 1], "layers": [{"type": "lstm", "units": 8}, {"type": "lstm", "units": 8}],
                         "output": {"units": 3, "activation": "softmax"}})
    validate("rnn", {"input_shape": [24, 1], "layers": [{"type": "lstm", "units": 8, "return_sequences": True},
                                                        {"type": "gru", "units": 8}],
                     "output": {"units": 3, "activation": "softmax"}})


def test_layer_not_allowed_in_family():
    with pytest.raises(ArchitectureError):
        validate("feedforward", {"input_shape": [2], "layers": [{"type": "conv2d", "filters": 2}], "output": {"units": 2, "activation": "softmax"}})


def test_limits_enforced():
    with pytest.raises(ArchitectureError):
        validate("feedforward", TPL["feedforward"], Limits(max_params=10))
    with pytest.raises(ArchitectureError):
        validate("feedforward", {**TPL["feedforward"], "layers": [{"type": "dense", "units": 9999}]})


def test_sigmoid_output_rules():
    with pytest.raises(ArchitectureError):
        validate("feedforward", {"input_shape": [2], "layers": [{"type": "dense", "units": 4}], "output": {"units": 2, "activation": "sigmoid"}})


def test_compatibility_checks_classes_and_shape():
    cfg, _ = validate("feedforward", TPL["feedforward"])
    assert compatibility("feedforward", cfg, builtin_metadata("espirales")) == []
    assert compatibility("feedforward", cfg, builtin_metadata("circulos"))  # 3 clases vs 2 salidas
    assert compatibility("feedforward", cfg, builtin_metadata("patrones8x8"))  # forma distinta
    gcfg, _ = validate("gan", TPL["gan"])
    assert compatibility("gan", gcfg, builtin_metadata("anillo2d")) == []
    assert compatibility("gan", gcfg, builtin_metadata("espirales"))


def test_state_machine():
    assert can_transition("QUEUED", "PREPARING")
    assert can_transition("QUEUED", "CANCELLED")
    assert can_transition("RUNNING", "COMPLETED")
    assert not can_transition("QUEUED", "COMPLETED")
    assert not can_transition("COMPLETED", "RUNNING")
    for t in TERMINAL:
        assert not any(can_transition(t, d) for d in ("QUEUED", "RUNNING", "PREPARING"))


def test_permissions_matrix():
    assert Perm.TRAIN in ROLE_PERMS["engineer"] and Perm.TRAIN not in ROLE_PERMS["reviewer"]
    assert Perm.REVIEW_MODEL in ROLE_PERMS["reviewer"] and Perm.REVIEW_MODEL not in ROLE_PERMS["engineer"]
    assert ROLE_PERMS["reader"] == {Perm.VIEW}
    assert ROLE_PERMS["lead"] == set(Perm)


def test_csv_parsing_valid_and_invalid():
    rows = "a,b,clase\n" + "\n".join(f"{i},{i * 2},{'x' if i % 2 else 'y'}" for i in range(30))
    meta = parse_csv(rows.encode(), None)
    assert meta["num_classes"] == 2 and meta["input_shape"] == [2]
    X, y = load_arrays(meta, rows.encode())
    assert X.shape == (30, 2) and abs(float(X.mean())) < 1e-5  # estandarizado
    for bad in [b"a,b\n1,2\n", ("a,b\n" + "\n".join("1,x" for _ in range(30))).encode(), b"\x00\x01binario",
                ("a,b\n" + "\n".join(f"{i},z" for i in range(30))).encode()]:
        with pytest.raises(DatasetError):
            parse_csv(bad, None)


def test_builtin_datasets_split():
    for key in ("espirales", "patrones8x8", "ondas", "anillo2d"):
        X, y = load_arrays(builtin_metadata(key))
        (a, _), (b, _), (c, _) = split_arrays(X, y)
        assert len(a) + len(b) + len(c) == len(X) and len(b) > 0 and len(c) > 0


def test_supabase_storage_headers(monkeypatch):
    """Las secret keys nuevas van solo en apikey; la service_role legada (JWT) también en Authorization."""
    import httpx
    from app.modules.storage import SupabaseStorage
    seen = []

    class R:
        status_code, text, content = 200, "", b"ok"

    monkeypatch.setattr(httpx, "post", lambda url, **kw: seen.append((url, kw["headers"])) or R())
    monkeypatch.setattr(httpx, "get", lambda url, **kw: seen.append((url, kw["headers"])) or R())
    SupabaseStorage("https://x.supabase.co", "sb_secret_abc", "b").put("k/a.csv", b"1")
    assert "Authorization" not in seen[-1][1] and seen[-1][1]["apikey"] == "sb_secret_abc"
    assert seen[-1][0] == "https://x.supabase.co/storage/v1/object/b/k/a.csv"
    SupabaseStorage("https://x.supabase.co", "eyJlegacy", "b").get("k")
    assert seen[-1][1]["Authorization"] == "Bearer eyJlegacy"


def test_supabase_jwt_verification(monkeypatch):
    """Tokens ES256 de Supabase se validan con JWKS: firma, emisor, audiencia y expiración."""
    import time

    import jwt
    from cryptography.hazmat.primitives.asymmetric import ec
    from fastapi import HTTPException

    from app.core import auth
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(auth.settings, "auth_mode", "supabase")
    monkeypatch.setattr(auth.settings, "supabase_url", "https://ref.supabase.co")

    class K:
        def get_signing_key_from_jwt(self, token):
            return type("SK", (), {"key": key.public_key()})()

    monkeypatch.setattr(auth, "_jwks", lambda: K())
    now = int(time.time())
    base = {"sub": "u-1", "email": "Ana@X.dev", "aud": "authenticated", "iss": "https://ref.supabase.co/auth/v1",
            "exp": now + 60, "user_metadata": {"full_name": "Ana Q"}}
    ok = auth.decode_token(jwt.encode(base, key, "ES256", headers={"kid": "k1"}))
    assert ok.subject == "u-1" and ok.email == "ana@x.dev" and ok.name == "Ana Q"
    for bad in ({**base, "iss": "https://otro.supabase.co/auth/v1"}, {**base, "aud": "anon"}, {**base, "exp": now - 10}):
        with pytest.raises(HTTPException):
            auth.decode_token(jwt.encode(bad, key, "ES256", headers={"kid": "k1"}))
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(HTTPException):
        auth.decode_token(jwt.encode(base, other, "ES256", headers={"kid": "k1"}))
