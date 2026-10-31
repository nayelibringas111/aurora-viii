"""Integración API + PostgreSQL, seguridad y flujo end-to-end con entrenamiento real en TensorFlow/Keras."""
import io
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core.db import SessionLocal
from app.models import TrainingJob

P = "/api/v1"


def _job(client, h, project, arch, ds, epochs=4, **params):
    return client.post(f"{P}/projects/{project['id']}/training-jobs", headers=h, json={
        "architecture_id": arch["id"], "dataset_id": ds["id"],
        "params": {"epochs": epochs, "batch_size": 64, "learning_rate": 0.02, "observe": False, **params}})


def test_requires_auth(client):
    assert client.get(f"{P}/projects").status_code == 401
    assert client.get(f"{P}/projects", headers={"Authorization": "Bearer basura"}).status_code == 401
    assert client.get(f"{P}/auth/config").status_code == 200


def test_project_crud_and_search(client, admin):
    p = client.post(f"{P}/projects", headers=admin, json={"name": "Visión", "tags": ["CNN", "cnn", " Demo "]}).json()
    assert p["tags"] == ["cnn", "demo"] and p["my_role"] == "lead"
    assert any(x["id"] == p["id"] for x in client.get(f"{P}/projects?q=Visi", headers=admin).json())
    r = client.patch(f"{P}/projects/{p['id']}", headers=admin, json={"status": "archived"})
    assert r.json()["status"] == "archived"
    assert client.post(f"{P}/projects", headers=admin, json={"name": "x"}).status_code == 422


def test_horizontal_access_is_blocked(client, admin, login, project, ff_arch, datasets):
    eve = login("eve@aurora-lab.dev", "Eve")
    job = _job(client, admin, project, ff_arch, datasets["Espirales entrelazadas"]).json()
    assert client.get(f"{P}/projects/{project['id']}", headers=eve).status_code == 404
    assert client.get(f"{P}/training-jobs/{job['job_id']}", headers=eve).status_code == 404
    assert client.post(f"{P}/training-jobs/{job['job_id']}/cancel", headers=eve).status_code == 404
    assert client.get(f"{P}/training-jobs/{job['job_id']}/events", headers=eve).status_code == 404
    assert all(p["id"] != project["id"] for p in client.get(f"{P}/projects", headers=eve).json())
    client.post(f"{P}/training-jobs/{job['job_id']}/cancel", headers=admin)


def test_roles_enforced(client, admin, login, project, ff_arch, datasets):
    rev = login("rev@aurora-lab.dev", "Revisora")
    reader = login("lector@aurora-lab.dev", "Lector")
    client.put(f"{P}/projects/{project['id']}/members", headers=admin, json={"email": "rev@aurora-lab.dev", "role": "reviewer"})
    client.put(f"{P}/projects/{project['id']}/members", headers=admin, json={"email": "lector@aurora-lab.dev", "role": "reader"})
    assert client.get(f"{P}/projects/{project['id']}", headers=reader).status_code == 200
    assert _job(client, rev, project, ff_arch, datasets["Espirales entrelazadas"]).status_code == 403
    assert client.get(f"{P}/projects/{project['id']}/export.csv", headers=reader).status_code == 403
    assert client.get(f"{P}/projects/{project['id']}/export.csv", headers=rev).status_code == 200
    assert client.get(f"{P}/projects/{project['id']}/audit-events", headers=reader).status_code == 403
    assert client.get(f"{P}/admin/users", headers=rev).status_code == 403
    # el propietario no puede ser degradado
    owner_email = "admin@aurora-lab.dev"
    assert client.put(f"{P}/projects/{project['id']}/members", headers=admin, json={"email": owner_email, "role": "reader"}).status_code == 409


def test_invalid_architecture_rejected_server_side(client, admin, project):
    r = client.post(f"{P}/projects/{project['id']}/architectures", headers=admin, json={
        "name": "mala", "family": "cnn", "config": {"input_shape": [8, 8, 1], "layers": [{"type": "dense", "units": 4}], "output": {"units": 4, "activation": "softmax"}}})
    assert r.status_code == 422 and r.json()["detail"]["issues"]


def test_architecture_versioning(client, admin, project, ff_arch):
    from app.modules.catalog import FAMILIES
    tpl = FAMILIES[0]["template"]
    again = client.post(f"{P}/projects/{project['id']}/architectures", headers=admin, json={"name": "ff", "family": "feedforward", "config": tpl}).json()
    assert again["version"] == ff_arch["version"] + 1


def test_incompatible_dataset_and_limits(client, admin, project, ff_arch, datasets):
    r = _job(client, admin, project, ff_arch, datasets["Anillos concéntricos (3 clases)"])
    assert r.status_code == 422
    r = _job(client, admin, project, ff_arch, datasets["Espirales entrelazadas"], epochs=999999)
    assert r.status_code == 422  # validación de esquema (le=5000) o límite configurado


def test_cancel_queued_job_and_terminal_conflict(client, admin, project, ff_arch, datasets):
    jid = _job(client, admin, project, ff_arch, datasets["Espirales entrelazadas"]).json()["job_id"]
    r = client.post(f"{P}/training-jobs/{jid}/cancel", headers=admin, json={"reason": "prueba"})
    assert r.json()["status"] == "CANCELLED"
    assert client.post(f"{P}/training-jobs/{jid}/cancel", headers=admin).status_code == 409
    retry = client.post(f"{P}/training-jobs/{jid}/retry", headers=admin)
    assert retry.status_code == 202
    client.post(f"{P}/training-jobs/{retry.json()['job_id']}/cancel", headers=admin)


def test_quota_per_user(client, admin, login, project, ff_arch, datasets):
    eng = login("ing@aurora-lab.dev", "Ingeniera")
    client.put(f"{P}/projects/{project['id']}/members", headers=admin, json={"email": "ing@aurora-lab.dev", "role": "engineer"})
    ds = datasets["Espirales entrelazadas"]
    ids = [_job(client, eng, project, ff_arch, ds).json()["job_id"] for _ in range(2)]
    assert _job(client, eng, project, ff_arch, ds).status_code == 429
    for j in ids:
        client.post(f"{P}/training-jobs/{j}/cancel", headers=eng)


def test_csv_upload_validation(client, admin, project):
    good = "x1,x2,y\n" + "\n".join(f"{i * 0.1},{i % 3},{'a' if i % 2 else 'b'}" for i in range(40))
    r = client.post(f"{P}/projects/{project['id']}/datasets", headers=admin, data={"name": "mi-csv"},
                    files={"file": ("datos.csv", io.BytesIO(good.encode()), "text/csv")})
    assert r.status_code == 201 and r.json()["num_classes"] == 2
    bad = client.post(f"{P}/projects/{project['id']}/datasets", headers=admin, data={"name": "malo"},
                      files={"file": ("malo.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")})
    assert bad.status_code == 422
    exe = client.post(f"{P}/projects/{project['id']}/datasets", headers=admin, data={"name": "exe"},
                      files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
    assert exe.status_code == 415
    d = r.json()
    assert client.delete(f"{P}/projects/{project['id']}/datasets/{d['id']}", headers=admin).json()["ok"]


def test_end_to_end_training_flow(client, admin, project, ff_arch, datasets):
    """crear proyecto → diseñar red → entrenar (TF real) → métricas → versión de modelo → reportes."""
    from aurora_worker.runner import run_loop
    jid = _job(client, admin, project, ff_arch, datasets["Espirales entrelazadas"], epochs=5).json()["job_id"]
    run_loop(once=True)
    job = client.get(f"{P}/training-jobs/{jid}", headers=admin).json()
    assert job["status"] == "COMPLETED", job["error_message"]
    assert job["topology"]["groups"][0]["layers"][0]["kind"] == "input"
    assert {"groups", "sample", "boundary"} <= set(job["snapshot"])
    metrics = client.get(f"{P}/training-jobs/{jid}/metrics", headers=admin).json()
    assert len(metrics["epochs"]) == 5 and "val_accuracy" in metrics["epochs"][0]
    models = client.get(f"{P}/projects/{project['id']}/models", headers=admin).json()
    m = next(x for x in models if x["job_id"] == jid)
    assert m["status"] == "draft" and len(m["checksum"]) == 64
    dl = client.get(f"{P}/models/{m['id']}/download", headers=admin)
    import hashlib
    assert hashlib.sha256(dl.content).hexdigest() == m["checksum"]
    assert client.patch(f"{P}/models/{m['id']}/status", headers=admin, json={"status": "approved"}).status_code == 409
    assert client.patch(f"{P}/models/{m['id']}/status", headers=admin, json={"status": "reviewed"}).status_code == 200
    assert client.patch(f"{P}/models/{m['id']}/status", headers=admin, json={"status": "approved"}).status_code == 200
    # SSE: reanudación desde un id intermedio devuelve solo lo posterior
    full = client.get(f"{P}/training-jobs/{jid}/events", headers=admin).text
    ids = [int(l[4:]) for l in full.splitlines() if l.startswith("id: ")]
    part = client.get(f"{P}/training-jobs/{jid}/events", headers={**admin, "Last-Event-ID": str(ids[len(ids) // 2])}).text
    assert part.count("\nid: ") + part.startswith("id: ") < len(ids) and "event: end" in part
    assert client.get(f"{P}/projects/{project['id']}/report.pdf", headers=admin).content[:4] == b"%PDF"
    cmp = client.get(f"{P}/projects/{project['id']}/compare?jobs={jid}", headers=admin).json()
    assert cmp[0]["epochs"]
    actions = {a["action"] for a in client.get(f"{P}/projects/{project['id']}/audit-events", headers=admin).json()}
    assert {"training.started", "model.status_changed", "model.exported", "report.exported"} <= actions


def test_worker_crash_recovery(client, admin, project, ff_arch, datasets):
    """Un trabajo con heartbeat vencido se reencola sin perder el estado persistido."""
    from aurora_worker.runner import reclaim_stale
    jid = _job(client, admin, project, ff_arch, datasets["Espirales entrelazadas"]).json()["job_id"]
    with SessionLocal() as db:
        db.execute(update(TrainingJob).where(TrainingJob.id == jid).values(
            status="RUNNING", attempt=1, heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10)))
        db.commit()
    reclaim_stale()
    assert client.get(f"{P}/training-jobs/{jid}", headers=admin).json()["status"] == "QUEUED"
    with SessionLocal() as db:
        db.execute(update(TrainingJob).where(TrainingJob.id == jid).values(
            status="RUNNING", attempt=2, heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10)))
        db.commit()
    reclaim_stale()
    j = client.get(f"{P}/training-jobs/{jid}", headers=admin).json()
    assert j["status"] == "FAILED" and "reintentos" in j["error_message"]


def test_cooperative_cancel_while_running(client, admin, project, ff_arch, datasets):
    from aurora_worker import runner
    jid = _job(client, admin, project, ff_arch, datasets["Espirales entrelazadas"], epochs=150, observe=True).json()["job_id"]
    wid = "test-worker"
    claimed = runner.claim_next(wid)
    assert str(claimed) == jid
    with SessionLocal() as db:  # el usuario pide cancelar mientras corre
        db.execute(update(TrainingJob).where(TrainingJob.id == jid).values(cancel_requested=True, cancel_reason="prueba"))
        db.commit()
    runner.run_job(claimed, wid)
    j = client.get(f"{P}/training-jobs/{jid}", headers=admin).json()
    assert j["status"] == "CANCELLED" and j["current_epoch"] < 150


def test_admin_limits_and_health(client, admin):
    r = client.put(f"{P}/admin/limits", headers=admin, json={"values": {"max_epochs": 50}})
    assert r.json()["values"]["max_epochs"] == 50
    assert client.put(f"{P}/admin/limits", headers=admin, json={"values": {"max_epochs": 0}}).status_code == 422
    assert client.get(f"{P}/admin/health", headers=admin).json()["database"]["ok"]
    client.put(f"{P}/admin/limits", headers=admin, json={"values": {"max_epochs": 200}})
